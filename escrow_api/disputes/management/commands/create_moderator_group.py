from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model
from disputes.models import Dispute, DisputeMessage

User = get_user_model()

class Command(BaseCommand):
    help = "Creates a 'Moderators' group and assigns dispute permissions. Optionally assign a user."

    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, help='Email of user to assign to Moderators group')

    def handle(self, *args, **options):
        group_name = "Moderators"
        permissions_needed = ["view_dispute", "change_dispute", "view_disputemessage", "change_disputemessage"]

        group, created = Group.objects.get_or_create(name=group_name)
        
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created group: {group_name}"))
        else:
            self.stdout.write(f"Group '{group_name}' already exists.")

        ct_dispute = ContentType.objects.get_for_model(Dispute)
        dispute_perms = Permission.objects.filter(content_type=ct_dispute, codename__in=permissions_needed)
        
        ct_disputemessage = ContentType.objects.get_for_model(DisputeMessage)
        dispute_message_perms = Permission.objects.filter(content_type=ct_disputemessage, codename__in=permissions_needed)
        
        all_perms = list(dispute_perms) + list(dispute_message_perms)
        for perm in all_perms:
            group.permissions.add(perm)

        self.stdout.write(self.style.SUCCESS("Assigned Dispute and DisputeMessage permissions to Moderators group."))

        email = options['email']
        if email:
            try:
                user = User.objects.get(email=email)
                user.groups.add(group)
                self.stdout.write(self.style.SUCCESS(f"User {email} added to Moderators group."))
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"User with email {email} does not exist."))
