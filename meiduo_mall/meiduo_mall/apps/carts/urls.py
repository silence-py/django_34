from django.conf.urls import url
from . import views

urlpatterns = [

    url(r'^carts/$', views.CartView.as_view()),   # 购物车路由

    url(r'^carts/selection/$', views.CartSelectedAllView.as_view()),   # 购物车全选

    url(r'^carts/simple/$', views.CartSimpleView.as_view()),   # 简单版购物车

]