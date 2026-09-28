from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .models import Certificate, JudgeCertificate


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


@require_GET
def judge_certificate_view(request, public_id):
    """T4 spec: signed, verifiable judge participation record.

    Same URL shape and signature scheme as the submission certificate
    endpoint so the verification flow is identical on the receiver side.
    The signed payload includes the judge's assignments and submitted
    reviews, plus per-criterion aggregates — enough to prove a judge
    participated without needing to call back to the API.
    """
    try:
        cert = JudgeCertificate.objects.select_related("judge", "event").get(
            public_id=public_id
        )
    except JudgeCertificate.DoesNotExist:
        return JsonResponse(
            {"error": {"code": "not_found", "message": "No such participation record."}},
            status=404,
        )

    if not cert.verify():
        return JsonResponse(
            {"error": {"code": "signature_invalid", "message": "Signature does not verify."}},
            status=400,
        )

    return JsonResponse(
        {
            "public_id": cert.public_id,
            "judge_email": cert.judge.email,
            "event_slug": cert.event.slug,
            "issued_at": cert.issued_at.isoformat(),
            "updated_at": cert.updated_at.isoformat(),
            "signed_payload": cert.signed_payload,
            "signature": cert.signature,
            "signature_algorithm": "HMAC-SHA256",
        }
    )
