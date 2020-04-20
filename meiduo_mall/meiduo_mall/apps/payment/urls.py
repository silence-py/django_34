from django.conf.urls import url
from . import views

urlpatterns = [

    url(r'^payment/(?P<order_id>\d+)/$', views.PaymentURLView.as_view()),   # 订单支付路由

    url(r'^payment/status/$', views.PaymentSuccessView.as_view()),   # 支付成功路由

]