from django.conf.urls import url
from . import views

urlpatterns = [

    # 收货地区路由
    url(r'^areas/$', views.AreaView.as_view()),


]