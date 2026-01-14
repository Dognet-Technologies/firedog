"""
Integrity Monitor per Dog Agent
Verifica integrità file con SHA512
"""
import hashlib
import logging
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)


class IntegrityMonitor:
    """Monitora integrità file critici"""

    def __init__(self, monitored_files: List[str]):
        """
        Args:
            monitored_files: Lista path file da monitorare
        """
        self.monitored_files = [Path(f) for f in monitored_files]
        self.hashes = {}
        self.initialize_hashes()

    def initialize_hashes(self):
        """Calcola hash iniziali dei file"""
        for file_path in self.monitored_files:
            if file_path.exists():
                self.hashes[str(file_path)] = self.calculate_hash(file_path)
                logger.info(f"Initialized hash for {file_path}")
            else:
                logger.warning(f"File not found for monitoring: {file_path}")

    @staticmethod
    def calculate_hash(file_path: Path) -> str:
        """Calcola SHA512 hash di un file"""
        try:
            sha512 = hashlib.sha512()
            with open(file_path, 'rb') as f:
                while chunk := f.read(8192):
                    sha512.update(chunk)
            return sha512.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating hash for {file_path}: {e}")
            return ""

    def check_integrity(self) -> List[Dict]:
        """
        Verifica integrità di tutti i file
        Returns: Lista di file modificati
        """
        modified_files = []

        for file_path in self.monitored_files:
            if not file_path.exists():
                modified_files.append({
                    'file': str(file_path),
                    'status': 'deleted',
                    'old_hash': self.hashes.get(str(file_path), ''),
                    'new_hash': ''
                })
                continue

            current_hash = self.calculate_hash(file_path)
            stored_hash = self.hashes.get(str(file_path))

            if stored_hash and current_hash != stored_hash:
                modified_files.append({
                    'file': str(file_path),
                    'status': 'modified',
                    'old_hash': stored_hash,
                    'new_hash': current_hash
                })
                logger.warning(f"File integrity violation: {file_path}")

                # Aggiorna hash
                self.hashes[str(file_path)] = current_hash

        return modified_files

    def update_hash(self, file_path: str):
        """Aggiorna hash di un file specifico"""
        path = Path(file_path)
        if path.exists():
            self.hashes[file_path] = self.calculate_hash(path)
            logger.info(f"Updated hash for {file_path}")
