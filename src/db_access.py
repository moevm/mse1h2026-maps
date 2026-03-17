from mainapp.models import TopicRequest

def put_request(topic):
    if not topic or not isinstance(topic, str):
        raise ValueError("topic должна быть непустой строкой")

    obj = TopicRequest.objects.create(topic=topic)
    return obj.id


def get_request(request_id) -> TopicRequest:
    try:
        obj = TopicRequest.objects.get(id=request_id)
        return obj

    except TopicRequest.DoesNotExist:
        return None