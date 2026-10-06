from rest_framework.response import Response


def ok(data, status=200):
    return Response({"data": data}, status=status)


def fail(code, fields=None, status=400):
    payload = {"error": {"code": code}}
    if fields:
        payload["error"]["fields"] = fields
    return Response(payload, status=status)
