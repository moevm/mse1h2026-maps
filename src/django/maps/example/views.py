from django.http import HttpResponse
from django.contrib.auth.models import User


def index(request):

    """
    user = User.objects.create_user(
        username='TEST_USER',
        password='12345',
        email='ivan@example.com'
    )
    """

    if request.user.is_authenticated:
        user = request.user
        print(user.id)
        print(user.password)
        print(type(user))
        print("YES")  # Вывод в консоль сервера

    return HttpResponse("PLACEHOLDER")