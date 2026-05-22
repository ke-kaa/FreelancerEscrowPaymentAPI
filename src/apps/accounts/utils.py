from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import send_mail
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.conf import settings
from django.urls import reverse


def generate_password_reset_link(user, request=None):
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token_generator = PasswordResetTokenGenerator()
    token = token_generator.make_token(user)
    reset_path = reverse('password-reset-confirm')
    reset_url = f"{settings.FRONTEND_DOMAIN}/reset-password?uid={uidb64}&token={token}"
    
    return reset_url, token

def send_reset_email(user, reset_url):
    subject = "Password Reset Request"
    message = f"""
    Hello {user.get_username() or user.email},
    
    You're receiving this email because you requested a password reset for your account.
    
    Please click the link below to reset your password:
    {reset_url}
    
    If you didn't request this, please ignore this email.
    
    Thanks,
    The {settings.SITE_NAME} Team
    """
    
    # Send email using your SMTP backend
    send_mail(
        subject=subject,
        message=message.strip(),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


def generate_reactivation_link(user):
    token = PasswordResetTokenGenerator().make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    url = f'{settings.FRONTEND_DOMAIN}/reactivate-account?uid={uid}&token={token}'

    return url, token, uid


def send_reactivation_email(user, reactivation_link):
    subject = "Reactivate Your Account"
    message = f"""
    Hi {user.get_full_name() or user.email},

    You requested to reactivate your account.

    Click the link below to proceed:
    {reactivation_link}

    If you didn’t request this, just ignore this email.

    — {settings.SITE_NAME} Team
    """
    send_mail(
        subject=subject,
        message=message.strip(),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False
    )