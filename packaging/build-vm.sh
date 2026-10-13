#!/usr/bin/env bash
#
# FireDog — VM appliance builder
#
# Produce in dist/:
#   firedog-<versione>-linux-x86_64.qcow2   (KVM / Proxmox)
#   firedog-<versione>-linux-x86_64.ova      (VirtualBox / VMware)
#
# Il tarball di release (dist/*.tar.gz) deve esistere prima di chiamare
# questo script. Eseguilo su un host Linux x86_64.
#
# Uso:
#   packaging/build-vm.sh [versione]   # versione default = git describe
#
# Dipendenze sul build host (una tantum):
#   sudo apt-get install qemu-system-x86 qemu-utils cloud-image-utils virtualbox
#   (genisoimage o mkisofs come fallback per il cloud-init ISO)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

VERSION="${1:-$(git describe --tags --always 2>/dev/null || echo v0.0.0)}"
ARCH="linux-x86_64"
TARBALL_NAME="firedog-${VERSION}-${ARCH}.tar.gz"
TARBALL="$REPO_ROOT/dist/$TARBALL_NAME"
OUT="$REPO_ROOT/dist"
VM_NAME="firedog-${VERSION}-${ARCH}"

# Immagine base: Debian 13 (trixie) generic cloud, sovrascrivibile via env
DEBIAN_IMG_URL="${DEBIAN_CLOUD_IMG_URL:-https://cloud.debian.org/images/cloud/trixie/latest/debian-13-genericcloud-amd64.qcow2}"
IMG_CACHE="${DEBIAN_CLOUD_IMG_CACHE:-$HOME/.cache/firedog-build/debian-13-cloud-amd64.qcow2}"

VM_RAM=2048    # MB (build)
VM_CPUS=2
DISK_SIZE=20G
BUILD_TIMEOUT=2400  # secondi — 40 min ceiling (TCG ~15-20 min, KVM ~5 min)
HTTP_PORT=18081

log() { echo -e "\n\033[1;36m▶  $*\033[0m"; }
die() { echo -e "\033[1;31mERRORE: $*\033[0m" >&2; exit 1; }

# ── Prerequisiti ─────────────────────────────────────────────────────────────
log "Controllo prerequisiti"

[ -f "$TARBALL" ] || die "Tarball non trovato: $TARBALL
       Esegui prima: packaging/build-release.sh $VERSION"

for cmd in qemu-system-x86_64 qemu-img wget python3; do
    command -v "$cmd" >/dev/null || die "Comando non trovato: $cmd
       sudo apt-get install qemu-system-x86 qemu-utils"
done

ISO_CMD=""
for c in cloud-localds genisoimage mkisofs; do
    command -v "$c" >/dev/null && { ISO_CMD="$c"; break; }
done
[ -n "$ISO_CMD" ] || die "Serve cloud-localds, genisoimage o mkisofs per il cloud-init ISO.
       sudo apt-get install cloud-image-utils"

KVM_FLAGS="-smp $VM_CPUS"
# Nota: KVM causa entry failures random su kernel 6.19+ con QEMU 10.x (CR3=0
# state corruption) — stesso bug già affrontato per SentinelCore. TCG di
# default, KVM solo se esplicitamente richiesto.
if [ -w /dev/kvm ] && [ "${BUILD_USE_KVM:-0}" = "1" ]; then
    KVM_FLAGS="-enable-kvm -smp 1"
    echo "  KVM abilitato (BUILD_USE_KVM=1)"
else
    echo "  Emulazione software TCG (affidabile su kernel 6.19+, ~15 min)"
fi

# ── Workspace ────────────────────────────────────────────────────────────────
WORK_DIR="$(mktemp -d)"
HTTP_PID=""
QEMU_PID=""

cleanup() {
    [ -n "$HTTP_PID"  ] && kill "$HTTP_PID"  2>/dev/null || true
    [ -n "$QEMU_PID"  ] && kill "$QEMU_PID"  2>/dev/null || true
    rm -rf "$WORK_DIR"
}
trap cleanup EXIT

# ── 1. Immagine base Debian 13 ───────────────────────────────────────────────
log "1/7  Immagine base Debian 13"
mkdir -p "$(dirname "$IMG_CACHE")"
if [ ! -f "$IMG_CACHE" ]; then
    echo "  Download: $DEBIAN_IMG_URL"
    wget --tries=3 --timeout=120 --progress=bar:force \
        -O "$IMG_CACHE.tmp" "$DEBIAN_IMG_URL" && mv "$IMG_CACHE.tmp" "$IMG_CACHE"
fi
cp "$IMG_CACHE" "$WORK_DIR/disk.qcow2"
qemu-img resize "$WORK_DIR/disk.qcow2" "$DISK_SIZE" >/dev/null
echo "  Disco pronto: $(qemu-img info "$WORK_DIR/disk.qcow2" | grep 'virtual size')"

# ── 2. HTTP server locale ────────────────────────────────────────────────────
log "2/7  HTTP server locale (build host → VM via NAT 10.0.2.2)"
fuser -k "${HTTP_PORT}/tcp" 2>/dev/null || true
sleep 1
python3 -m http.server --directory "$REPO_ROOT" "$HTTP_PORT" >/dev/null 2>&1 &
HTTP_PID=$!
echo "  PID $HTTP_PID   http://10.0.2.2:${HTTP_PORT}/dist/${TARBALL_NAME}"

# ── 3. Cloud-init ISO ────────────────────────────────────────────────────────
log "3/7  Cloud-init ISO"
CIDIR="$WORK_DIR/cidata"
mkdir -p "$CIDIR"

cat > "$CIDIR/meta-data" <<META
instance-id: firedog-build-$(date +%s)
local-hostname: firedog
META

cat > "$CIDIR/user-data" <<CLOUDINIT
#cloud-config
write_files:
  - path: /tmp/build-env.sh
    permissions: '0644'
    content: |
      export TARBALL_NAME="${TARBALL_NAME}"
      export HTTP_BASE="http://10.0.2.2:${HTTP_PORT}"
runcmd:
  - 'wget -q "http://10.0.2.2:${HTTP_PORT}/packaging/appliance/provision.sh" -O /tmp/provision.sh && chmod +x /tmp/provision.sh'
  - 'bash -c ". /tmp/build-env.sh && /tmp/provision.sh" > /var/log/firedog-provision.log 2>&1'
CLOUDINIT

case "$ISO_CMD" in
    cloud-localds)
        cloud-localds "$WORK_DIR/cidata.iso" "$CIDIR/user-data" "$CIDIR/meta-data"
        ;;
    genisoimage|mkisofs)
        "$ISO_CMD" -output "$WORK_DIR/cidata.iso" -volid cidata -joliet -rock \
            "$CIDIR/user-data" "$CIDIR/meta-data" 2>/dev/null
        ;;
esac
echo "  ISO: $WORK_DIR/cidata.iso"

# ── 4. Boot QEMU per il provisioning ────────────────────────────────────────
log "4/7  Provisioning VM (attendi ~5-20 min)"
# shellcheck disable=SC2086
qemu-system-x86_64 \
    -name "firedog-vm-build" \
    -m "$VM_RAM" \
    $KVM_FLAGS \
    -drive "file=$WORK_DIR/disk.qcow2,format=qcow2,if=virtio" \
    -drive "file=$WORK_DIR/cidata.iso,format=raw,if=virtio,readonly=on" \
    -netdev "user,id=net0,hostfwd=tcp::10023-:22" \
    -device "virtio-net-pci,netdev=net0" \
    -display none \
    -serial "file:$WORK_DIR/qemu-console.log" \
    -no-reboot \
    >/dev/null 2>&1 &
QEMU_PID=$!

echo -n "  Avanzamento: "
WAITED=0
while kill -0 "$QEMU_PID" 2>/dev/null; do
    sleep 5; WAITED=$((WAITED + 5))
    echo -n "."
    if [ "$WAITED" -ge "$BUILD_TIMEOUT" ]; then
        echo ""
        echo "TIMEOUT (${BUILD_TIMEOUT}s). Ultime righe console VM:"
        cp "$WORK_DIR/qemu-console.log" "$OUT/build-vm-console.log" 2>/dev/null || true
        tail -20 "$OUT/build-vm-console.log" 2>/dev/null || true
        kill "$QEMU_PID" 2>/dev/null || true
        die "Build VM non terminata. Log completo: $OUT/build-vm-console.log"
    fi
done
wait "$QEMU_PID" 2>/dev/null || true
echo " fatto"

cp "$WORK_DIR/qemu-console.log" "$OUT/build-vm-console.log" 2>/dev/null || true

# ── 5. qcow2 compresso ──────────────────────────────────────────────────────
log "5/7  Compressione immagine qcow2"
QCOW2_OUT="$OUT/${VM_NAME}.qcow2"
qemu-img convert -f qcow2 -O qcow2 -c \
    "$WORK_DIR/disk.qcow2" "$QCOW2_OUT"
echo "  $(ls -lh "$QCOW2_OUT" | awk '{print $5}')"

# ── 6. OVA (VirtualBox) via VBoxManage ──────────────────────────────────────
log "6/7  Generazione OVA (VBoxManage)"
OVA_OUT="$OUT/${VM_NAME}.ova"

command -v VBoxManage >/dev/null || die "VBoxManage non trovato.
       sudo apt-get install virtualbox  oppure installa VirtualBox da virtualbox.org"

VDI="$WORK_DIR/${VM_NAME}.vdi"
VBOX_VM="fd-ova-export-$$"

echo "  Conversione qcow2 → VDI..."
qemu-img convert -f qcow2 -O vdi "$QCOW2_OUT" "$VDI"
echo "  VDI: $(ls -lh "$VDI" | awk '{print $5}')"

echo "  Creazione VM temporanea VirtualBox..."
HOST_IFACE="$(ip route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="dev"){print $(i+1); exit}}')"
[ -z "$HOST_IFACE" ] && HOST_IFACE="eth0"
echo "  Bridge adapter: $HOST_IFACE"
VBoxManage createvm --name "$VBOX_VM" --ostype Debian_64 --register
VBoxManage modifyvm "$VBOX_VM" \
    --memory 2048 --cpus 2 \
    --nic1 bridged --bridgeadapter1 "$HOST_IFACE" --nictype1 virtio
VBoxManage storagectl "$VBOX_VM" --name "SATA" --add sata --controller IntelAhci
VBoxManage storageattach "$VBOX_VM" \
    --storagectl "SATA" --port 0 --device 0 \
    --type hdd --medium "$VDI"

echo "  Export OVA nativa..."
rm -f "$OVA_OUT"
VBoxManage export "$VBOX_VM" \
    --output "$OVA_OUT" \
    --ovf20 \
    --vsys 0 --product "FireDog" \
    --vsys 0 --vendor "Dognet Technologies" \
    --vsys 0 --version "${VERSION}" \
    --vsys 0 --description "Credenziali iniziali e URL in /etc/motd al primo avvio. CPU: 2 core, RAM: 2 GB, disco: 20 GB. Rete: scheda bridge."

VBoxManage unregistervm "$VBOX_VM" --delete 2>/dev/null || true
echo "  $(ls -lh "$OVA_OUT" | awk '{print $5}')"

# ── 7. Checksum finali ───────────────────────────────────────────────────────
log "7/7  Checksum artefatti VM"
( cd "$OUT" && sha256sum "${VM_NAME}.qcow2" "${VM_NAME}.ova" \
    > "${VM_NAME}.sha256" )

if gpg --list-secret-keys >/dev/null 2>&1; then
    ( cd "$OUT" && gpg --armor --detach-sign --output "${VM_NAME}.sha256.asc" \
        "${VM_NAME}.sha256" ) && echo "  Firmato: ${VM_NAME}.sha256.asc"
else
    echo "  (nessuna chiave GPG — firma saltata)"
fi

# ── Riepilogo ────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════════════"
echo " Artefatti VM in: $OUT/"
ls -lh "$OUT/${VM_NAME}".{qcow2,ova,sha256} 2>/dev/null | awk '{printf "  %-8s %s\n", $5, $9}'
echo ""
echo " Build log VM:  $OUT/build-vm-console.log"
echo ""
echo " KVM/Proxmox:   $OUT/${VM_NAME}.qcow2"
echo " VirtualBox:    $OUT/${VM_NAME}.ova   (importa con File → Importa appliance)"
echo " VMware:        $OUT/${VM_NAME}.ova   (File → Open...)"
echo ""
echo " Al primo avvio: first-boot rigenera tutti i segreti e il certificato"
echo " TLS, stampa credenziali admin + URL in /etc/motd (SSH o console VM)."
echo "════════════════════════════════════════════════════════════════"
