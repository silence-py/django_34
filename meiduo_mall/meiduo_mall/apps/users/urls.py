from django.conf.urls import url
from . import views


urlpatterns = [
    url(r'^register/$', views.RegisterView.as_view()),  # 设置注册页面路由

    url(r'^usernames/(?P<username>[a-zA-Z0-9_-]{5,20})/count/$', views.UserNameCountView.as_view()),   # 用户名重复检测

    url(r'^mobiles/(?P<mobile>1[345789]\d{9})/count/$', views.MobileCountView.as_view()),   # 手机号码重复检测

    url(r'^login/$', views.LoginView.as_view()),   # 用户登录页面

    url(r'^logout/$', views.LogoutView.as_view()),   # 用户退出登录页面

    url(r'^info/$', views.InfoView.as_view()),   # 用户中心页面

    url(r'^emails/$', views.EmailView.as_view()),   # 用户邮箱

    url(r'^emails/verification/$', views.VerifyEmailView.as_view()),   # 验证邮箱

    url(r'^addresses/$', views.AddressView.as_view()),   # 收货地址

    url(r'^addresses/create/$', views.CreateAddressView.as_view()),   # 新增收货地址

    url(r'^addresses/(?P<id>\d+)/$', views.DeleteAddressView.as_view()),   # 删除收货地址

    url(r'^addresses/(?P<id>\d+)/default/$', views.DefaultAddressView.as_view()),   # 设置默认收货地址

    url(r'^addresses/(?P<id>\d+)/title/$', views.AddressTitleView.as_view()),   # 修改收货地址标题

    url(r'^password/$', views.PasswordView.as_view()),  # 修改用户密码

    url(r'^browse_histories/$', views.UserBrowserHistory.as_view()),  # 用户浏览记录路由

    url(r'^find_password/$', views.FindPasswordView.as_view()),  # 找回用户密码

    url(r'^accounts/(?P<username>[a-zA-Z0-9_-]{5,20})/sms/token/$', views.ImageToFindPasswordView.as_view()),  # 找回密码之图片验证码

    url(r'^sms_codes/$', views.SmsCodeToFindPasswordView.as_view()),  # 找回密码之发送短信验证码

    url(r'^accounts/(?P<username>[a-zA-Z0-9_-]{5,20})/password/token/$', views.CheckSmsToFindPasswordView.as_view()),  # 找回密码之校验短信验证码

    url(r'^users/(?P<user_id>\d+)/password/$', views.SetNewPasswordView.as_view()),  # 找回密码之设置新密码


]