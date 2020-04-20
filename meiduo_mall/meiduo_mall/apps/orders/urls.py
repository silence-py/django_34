from django.conf.urls import url
from . import views

urlpatterns = [

    url(r'^orders/settlement/$', views.OrderSettlementView.as_view()),   # 结算订单

    url(r'^orders/commit/$', views.OrderCommitView.as_view()),   # 提交订单

    url(r'^orders/success/$', views.OrderSuccessView.as_view()),   # 订单成功界面

    url(r'^orders/info/(?P<page>\d+)/$', views.ShowOrderView.as_view()),   # 我的订单

    url(r'^orders/comment/$', views.OrderCommentView.as_view()),   # 订单评价

]