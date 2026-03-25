from django.db import models


class TopicRequest(models.Model):
    topic = models.CharField(max_length=200)
    status = models.CharField(
        max_length=20, default="pending"
    )  # pending, processing, completed, error
    created_at = models.DateTimeField(auto_now_add=True)


class RawData(models.Model):
    topic_request = models.ForeignKey(TopicRequest, on_delete=models.CASCADE)
    source = models.CharField(max_length=50)  # wikidata, github, semantic_scholar
    data = models.JSONField()
    collected_at = models.DateTimeField(auto_now_add=True)
