from django.conf.urls import url
from . import views

urlpatterns = [

    url(r'^list/(?P<category_id>\d+)/(?P<page_num>\d+)/$', views.ListView.as_view()),   # 商品列表路由

    url(r'^hot/(?P<category_id>\d+)/$', views.HotGoodsView.as_view()),   # 热销商品路由

    url(r'^detail/(?P<sku_id>\d+)/$', views.DetailsGoodsView.as_view()),   # 商品详情路由

    url(r'^visit/(?P<category_id>\d+)/$', views.GoodVisitView.as_view()),   # 商品访问量路由

]