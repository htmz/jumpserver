import json
from importlib import import_module
import inspect

from django.utils.functional import LazyObject
from django.db.models.signals import post_save
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.apps import AppConfig

from notifications.backends import BACKEND
from users.models import User
from common.utils.connection import RedisPubSub
from common.utils import get_logger
from common.decorator import on_transaction_commit
from .models import SiteMessage, SystemMsgSubscription, UserMsgSubscription
from .notifications import SystemMessage


logger = get_logger(__name__)


def new_site_msg_pub_sub():
    return RedisPubSub('notifications.SiteMessageCome')


class NewSiteMsgSubPub(LazyObject):
    def _setup(self):
        self._wrapped = new_site_msg_pub_sub()


new_site_msg_chan = NewSiteMsgSubPub()


@receiver(post_save, sender=SiteMessage)
@on_transaction_commit
def on_site_message_create(sender, instance, created, **kwargs):
    if not created:
        return
    logger.debug('New site msg created, publish it')
    user_ids = instance.users.all().values_list('id', flat=True)
    user_ids = [str(i) for i in user_ids]
    data = {
        'id': str(instance.id),
        'subject': instance.subject,
        'message': instance.message,
        'users': user_ids
    }
    new_site_msg_chan.publish(data)


@receiver(post_migrate, dispatch_uid='notifications.signals_handler.create_system_messages')
def create_system_messages(app_config: AppConfig, **kwargs):
    try:
        notifications_module = import_module('.notifications', app_config.module.__package__)

        for name, obj in notifications_module.__dict__.items():
            if name.startswith('_'):
                continue

            if not inspect.isclass(obj):
                continue

            if not issubclass(obj, SystemMessage):
                continue

            attrs = obj.__dict__
            if 'message_type_label' not in attrs:
                continue

            if 'category' not in attrs:
                continue

            if 'category_label' not in attrs:
                continue

            message_type = obj.get_message_type()
            sub, created = SystemMsgSubscription.objects.get_or_create(message_type=message_type)
            if created:
                obj.post_insert_to_db(sub)
                logger.info(f'Create SystemMsgSubscription: package={app_config.module.__package__} type={message_type}')
    except ModuleNotFoundError:
        pass


@receiver(post_save, sender=User)
def on_user_post_save(sender, instance, created, **kwargs):
    if not created:
        return
    receive_backends = []
    # Todo: IDE 识别不了 get_account
    for backend in BACKEND:
        if backend.get_account(instance):
            receive_backends.append(backend)
    UserMsgSubscription.objects.create(user=instance, receive_backends=receive_backends)
