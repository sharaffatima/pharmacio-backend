from django.contrib.contenttypes.models import ContentType
from rbac.models import AuditLog

def create_audit_log(*, actor, action: str, entity=None, metadata=None, request=None):
 
    ct = None
    oid = None
    erepr = ""

    if entity is not None:
        ct = ContentType.objects.get_for_model(entity.__class__)
        oid = str(entity.pk)
        erepr = str(entity)[:255]

    AuditLog.objects.create(
        actor=actor,
        action=action,
        entity_content_type=ct,
        entity_object_id=oid,
        entity_repr=erepr,
        metadata=metadata or {},
    )