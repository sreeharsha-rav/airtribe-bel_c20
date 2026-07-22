from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import AuditLog, Document


@receiver(pre_save, sender=Document)
def stash_adding_state(sender, instance, **kwargs):
    # post_save always sees _state.adding == False (Django flips it before
    # firing the signal), so the create/update flag has to be captured here.
    instance._was_adding = instance._state.adding


@receiver(post_save, sender=Document)
def log_document_save(sender, instance, **kwargs):
    action = AuditLog.Action.CREATED if getattr(instance, '_was_adding', False) else AuditLog.Action.UPDATED
    AuditLog.objects.create(
        actor=instance.created_by,
        action=action,
        model_name='Document',
        object_id=str(instance.id),
    )
