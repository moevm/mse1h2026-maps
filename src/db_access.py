from mainapp.models import TopicRequest

from django.contrib.auth import get_user_model


def put_request(topic, author_id):
    if not topic or not isinstance(topic, str):
        raise ValueError("topic должна быть непустой строкой")
    User = get_user_model()
    author = User.objects.get(id=author_id)
    obj = TopicRequest.objects.create(topic=topic, author=author)
    return obj.id


def get_request(request_id) -> TopicRequest:
    try:
        obj = TopicRequest.objects.get(id=request_id)
        return obj

    except TopicRequest.DoesNotExist:
        return None
