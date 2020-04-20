"""meiduo_mall URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.11/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import url, include
from django.contrib import admin

urlpatterns = [
    url(r'^admin/', admin.site.urls),

    url(r'^', include('users.urls')),  # 设置用户应用路由

    url(r'^', include('verifications.urls')),   # 设置认证应用路由

    url(r'^', include('contents.urls')),  # 设置首页应用路由

    url(r'^', include('oauth.urls')),  # 设置QQ登录应用路由

    url(r'^', include('areas.urls')),  # 设置收获地区应用路由

    url(r'^', include('goods.urls')),  # 设置商品应用路由

    url(r'^', include('carts.urls')),  # 购物车应用路由

    url(r'^', include('orders.urls')),  # 订单结算应用路由

    url(r'^', include('payment.urls')),  # 订单支付路由

    url(r'^', include('sina.urls')),  # 微博登录路由


]
