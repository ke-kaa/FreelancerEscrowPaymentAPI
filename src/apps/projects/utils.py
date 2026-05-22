from django.core.mail import send_mail
from django.conf import settings


def send_proposal_accept_email(freelancer, proposal, ):
    subject = "Your Proposal Has Been Accepted"
    message = f"""
    Hello {freelancer.get_full_name() or freelancer.email},

    Congratulations! Your proposal for the project "{proposal.project.title}" has been accepted.

    
    Acceptance Time: {proposal.accepted_at.strftime('%Y-%m-%d %H:%M:%S')}

    You can now communicate with the client and start working.

    — The {settings.SITE_NAME} Team
    """

    send_mail(
        subject=subject,
        message=message.strip(),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[freelancer.email],
        fail_silently=False,
    )

