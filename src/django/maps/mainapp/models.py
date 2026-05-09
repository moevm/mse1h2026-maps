from django.conf import settings
from django.db import models


class TopicRequest(models.Model):
    topic = models.CharField(max_length=200)
    source_info = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20, default="pending"
    )  # pending, processing, completed, error
    created_at = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True
    )


class RawData(models.Model):
    topic_request = models.ForeignKey(TopicRequest, on_delete=models.CASCADE)
    source = models.CharField(max_length=50)  # wikidata, github, semantic_scholar
    data = models.JSONField()
    collected_at = models.DateTimeField(auto_now_add=True)
