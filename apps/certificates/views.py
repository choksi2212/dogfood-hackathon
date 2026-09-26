from django.http import JsonResponse
from django.views.decorators.http import require_GET

from apps.events.permissions import IsOrganizer
from apps.submissions.models import Submission

from .models import Certificate


@require_GET
def certificate_view(request, public_id):
    try:
        cert = Certificate.objects.select_related("submission").get(public_id=public_id)
    except Certificate.DoesNotExist:
        return JsonResponse({"error": {"code": "not_found", "message": "No such certificate."}}, status=404)

    if not cert.verify():
        return JsonResponse(
            {"error": {"code": "signature_invalid", "message": "Signature does not verify."}},
            status=400,
        )

    return JsonResponse(
        {
            "public_id": cert.public_id,
            "submission_id": str(cert.submission_id),
            "issued_at": cert.issued_at.isoformat(),
            "signed_payload": cert.signed_payload,
            "signature": cert.signature,
            "signature_algorithm": "HMAC-SHA256",
        }
    )
