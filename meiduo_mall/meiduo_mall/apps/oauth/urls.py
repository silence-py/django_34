from django.conf.urls import url
from . import views

urlpatterns = [

    # url(r'^qq/authorization/$', views.QQOAuthURLView.as_view()),  # QQ登录路由
    url(r'^qq/login/$', views.QQOAuthURLView.as_view()),  # QQ登录路由

    url(r'^oauth_callback$', views.QQOAuthUserView.as_view()),  # QQ登录回调路由

]