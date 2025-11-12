"""
Views per Discovery - Network scan e bulk import
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from django.utils import timezone 
import logging
from .models import DiscoveredHost
from .serializers import DiscoveredHostSerializer, DiscoveredHostListSerializer
from .tasks import discover_network_task
from targets.models import Target
from audit.models import AuditLog

logger = logging.getLogger('firedog.discovery')


class DiscoveredHostViewSet(viewsets.ModelViewSet):
    """ViewSet per gestione Discovered Hosts"""
    
    queryset = DiscoveredHost.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return DiscoveredHostListSerializer
        return DiscoveredHostSerializer
    
    def get_queryset(self):
        """Filter queryset based on query params"""
        queryset = super().get_queryset()
        
        # Filter by status
        is_alive = self.request.query_params.get('is_alive')
        if is_alive is not None:
            queryset = queryset.filter(is_alive=is_alive.lower() == 'true')
        
        is_imported = self.request.query_params.get('is_imported')
        if is_imported is not None:
            queryset = queryset.filter(is_imported=is_imported.lower() == 'true')
        
        # Filter by network
        network = self.request.query_params.get('network')
        if network:
            queryset = queryset.filter(network=network)
        
        # Search by IP or hostname
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(ip_address__icontains=search) |
                Q(hostname__icontains=search) |
                Q(vendor__icontains=search)
            )
        
        return queryset

    @action(detail=False, methods=['post'])
    def start_scan(self, request):
        """Avvia scan di rete (con Celery)"""
        try:
            logger.info(f"Network discovery started by user {request.user.id}")
            
            # Launch Celery task
            from discovery.tasks import discover_network_task
            task = discover_network_task.delay()
            
            # Audit log con helper method (OWASP compliance)
            try:
                AuditLog.log_action(
                    action='scan',
                    description='Network discovery scan started (ARP scan)',
                    user=request.user,
                    new_values={
                        'task_id': str(task.id),
                        'scan_type': 'arp',
                        'initiated_at': timezone.now().isoformat()
                    },
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')[:512],  # Truncate
                    success=True
                )
            except Exception as audit_error:
                logger.warning(f"Failed to create audit log: {audit_error}")
            
            return Response({
                'status': 'started',
                'task_id': str(task.id),
                'message': 'Network discovery scan avviata'
            })
            
        except Exception as e:
            error_msg = f"Failed to start network scan: {e}"
            logger.error(error_msg)
            
            # Audit log per errore (NIST compliance)
            try:
                AuditLog.log_action(
                    action='scan',
                    description='Network discovery scan failed to start',
                    user=request.user,
                    ip_address=request.META.get('REMOTE_ADDR'),
                    success=False,
                    error_message=str(e)
                )
            except Exception as audit_error:
                logger.warning(f"Failed to create error audit log: {audit_error}")
            
            return Response(
                {'error': error_msg},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def scan_status(self, request):
        """
        Ottieni status dello scan in corso
        
        GET /api/discovery/scan_status/?task_id=abc123
        
        Returns:
            {
                "status": "completed",
                "result": {...}
            }
        """
        from celery.result import AsyncResult
        
        task_id = request.query_params.get('task_id')
        if not task_id:
            return Response({
                'error': 'task_id parameter required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        task_result = AsyncResult(task_id)
        
        response = {
            'task_id': task_id,
            'status': task_result.state,
        }
        
        if task_result.ready():
            response['result'] = task_result.result
        
        return Response(response)
    
    @action(detail=False, methods=['get'])
    def get_results(self, request):
        """
        Ottieni risultati dell'ultimo scan
        
        GET /api/discovery/get_results/?not_imported=true
        
        Returns:
            {
                "count": 10,
                "hosts": [...]
            }
        """
        # Get discovered hosts not yet imported
        not_imported = request.query_params.get('not_imported', 'false').lower() == 'true'
        
        queryset = self.get_queryset()
        
        if not_imported:
            queryset = queryset.filter(is_imported=False, is_alive=True)
        
        # Order by last seen
        queryset = queryset.order_by('-last_seen')
        
        # Paginate
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = DiscoveredHostListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = DiscoveredHostListSerializer(queryset, many=True)
        return Response({
            'count': queryset.count(),
            'hosts': serializer.data
        })
    
    @action(detail=False, methods=['post'])
    def bulk_import(self, request):
        """
        Bulk import da file
        
        POST /api/discovery/bulk_import/
        Content-Type: multipart/form-data
        
        Body:
            file: <file.txt>
        
        File format (plain text):
            192.168.1.100 server01
            192.168.1.101 server02 Optional description
            192.168.1.102 server03
        
        Returns:
            {
                "imported": 5,
                "skipped": 2,
                "errors": [...]
            }
        """
        if 'file' not in request.FILES:
            return Response({
                'error': 'No file provided'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        file_obj = request.FILES['file']
        
        # Read file content
        try:
            content = file_obj.read().decode('utf-8')
        except UnicodeDecodeError:
            return Response({
                'error': 'File must be UTF-8 encoded text'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Parse file
        results = {
            'imported': 0,
            'skipped': 0,
            'errors': []
        }
        
        for line_num, line in enumerate(content.split('\n'), 1):
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            # Parse line: IP HOSTNAME [DESCRIPTION]
            parts = line.split(maxsplit=2)
            
            if len(parts) < 2:
                results['errors'].append({
                    'line': line_num,
                    'error': 'Invalid format (expected: IP HOSTNAME [DESCRIPTION])',
                    'content': line
                })
                continue
            
            ip_address = parts[0]
            hostname = parts[1]
            notes = parts[2] if len(parts) > 2 else ''
            
            # Validate IP
            import ipaddress
            try:
                ipaddress.ip_address(ip_address)
            except ValueError:
                results['errors'].append({
                    'line': line_num,
                    'error': f'Invalid IP address: {ip_address}',
                    'content': line
                })
                continue
            
            # Check if already exists as target
            already_target = Target.objects.filter(ip_address=ip_address).exists()
            
            # Create or update discovered host
            host, created = DiscoveredHost.objects.get_or_create(
                ip_address=ip_address,
                defaults={
                    'hostname': hostname,
                    'notes': notes,
                    'is_imported': already_target
                }
            )
            
            if created:
                results['imported'] += 1
                logger.info(f"Imported host from file: {ip_address} ({hostname})")
            else:
                # Update existing
                if not host.hostname:
                    host.hostname = hostname
                if notes and not host.notes:
                    host.notes = notes
                host.save()
                results['skipped'] += 1
        
        # Audit log
        AuditLog.objects.create(
            user=request.user,
            action='discovery_bulk_import',
            details=f'Bulk import: {results["imported"]} imported, {results["skipped"]} skipped'
        )
        
        logger.info(f"Bulk import completed: {results}")
        
        return Response(results, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def import_to_target(self, request, pk=None):
        """
        Importa discovered host come target
        
        POST /api/discovery/{id}/import_to_target/
        
        Body:
            {
                "hostname": "optional-override",
                "description": "optional description"
            }
        
        Returns:
            {
                "target_id": 123,
                "message": "Host imported as target"
            }
        """
        discovered_host = self.get_object()
        
        # Check if already imported
        if discovered_host.is_imported:
            return Response({
                'error': 'Host already imported as target'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if IP already exists as target
        if Target.objects.filter(ip_address=discovered_host.ip_address).exists():
            discovered_host.is_imported = True
            discovered_host.save()
            
            return Response({
                'error': 'IP address already exists as target'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create target
        hostname = request.data.get('hostname', discovered_host.hostname or f'host-{discovered_host.ip_address}')
        description = request.data.get('description', f'Imported from discovery - Vendor: {discovered_host.vendor}')
        
        target = Target.objects.create(
            ip_address=discovered_host.ip_address,
            hostname=hostname,
            description=description,
            status='pending'
        )
        
        # Mark as imported
        discovered_host.is_imported = True
        discovered_host.save()
        
        # Audit log
        AuditLog.objects.create(
            user=request.user,
            action='discovery_import_target',
            target=target,
            details=f'Imported from discovery: {discovered_host.ip_address}'
        )
        
        logger.info(f"Discovered host {discovered_host.id} imported as target {target.id}")
        
        return Response({
            'success': True,
            'target_id': target.id,
            'message': 'Host imported as target'
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['post'])
    def bulk_import_to_targets(self, request):
        """
        Importa multipli discovered hosts come targets
        
        POST /api/discovery/bulk_import_to_targets/
        
        Body:
            {
                "host_ids": [1, 2, 3, 4]
            }
        
        Returns:
            {
                "imported": 3,
                "skipped": 1,
                "errors": [...]
            }
        """
        host_ids = request.data.get('host_ids', [])
        
        if not host_ids:
            return Response({
                'error': 'host_ids array required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        results = {
            'imported': 0,
            'skipped': 0,
            'errors': []
        }
        
        for host_id in host_ids:
            try:
                discovered_host = DiscoveredHost.objects.get(id=host_id)
                
                # Skip if already imported
                if discovered_host.is_imported:
                    results['skipped'] += 1
                    continue
                
                # Skip if IP already exists
                if Target.objects.filter(ip_address=discovered_host.ip_address).exists():
                    discovered_host.is_imported = True
                    discovered_host.save()
                    results['skipped'] += 1
                    continue
                
                # Create target
                hostname = discovered_host.hostname or f'host-{discovered_host.ip_address}'
                
                target = Target.objects.create(
                    ip_address=discovered_host.ip_address,
                    hostname=hostname,
                    description=f'Imported from discovery - Vendor: {discovered_host.vendor}',
                    status='pending'
                )
                
                discovered_host.is_imported = True
                discovered_host.save()
                
                results['imported'] += 1
                
                logger.info(f"Bulk import: Host {host_id} imported as target {target.id}")
                
            except DiscoveredHost.DoesNotExist:
                results['errors'].append({
                    'host_id': host_id,
                    'error': 'Host not found'
                })
            except Exception as e:
                results['errors'].append({
                    'host_id': host_id,
                    'error': str(e)
                })
        
        # Audit log
        AuditLog.objects.create(
            user=request.user,
            action='discovery_bulk_import_targets',
            details=f'Bulk import to targets: {results["imported"]} imported, {results["skipped"]} skipped'
        )
        
        logger.info(f"Bulk import to targets completed: {results}")
        
        return Response(results, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'])
    def clear_old(self, request):
        """
        Rimuovi host non visti da X giorni
        
        POST /api/discovery/clear_old/
        
        Body:
            {
                "days": 30
            }
        """
        from django.utils.timezone import now
        from datetime import timedelta
        
        days = request.data.get('days', 30)
        
        cutoff_date = now() - timedelta(days=days)
        
        deleted_count = DiscoveredHost.objects.filter(
            last_seen__lt=cutoff_date,
            is_imported=False
        ).delete()[0]
        
        logger.info(f"Cleared {deleted_count} old discovered hosts (older than {days} days)")
        
        AuditLog.objects.create(
            user=request.user,
            action='discovery_clear_old',
            details=f'Cleared {deleted_count} hosts older than {days} days'
        )
        
        return Response({
            'success': True,
            'deleted': deleted_count
        })
