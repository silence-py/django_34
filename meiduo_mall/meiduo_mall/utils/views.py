from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View


class LoginRequiredView(LoginRequiredMixin, View):
    pass