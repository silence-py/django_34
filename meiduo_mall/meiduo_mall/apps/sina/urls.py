from django.conf.urls import url
from . import views

urlpatterns = [

    url(r'^sina/login/$', views.SinaLoginURLView.as_view()),   # 新浪微博登录链接

    url(r'^sina_callback/$', views.SinaOauthView.as_view()),   # 新浪微博回调链接

]