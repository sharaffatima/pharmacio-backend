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

    ip = None
    ua = ""
    if request is not None:
        ip = request.META.get("REMOTE_ADDR")
        ua = request.META.get("HTTP_USER_AGENT", "")[:2000]

    AuditLog.objects.create(
        actor=actor,
        action=action,
        entity_content_type=ct,
        entity_object_id=oid,
        entity_repr=erepr,
        metadata=metadata or {},
    )