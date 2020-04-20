# 保存常量数据
IMAGE_CODE_REDIS_EXPIRES = 300   # 图形验证码有效期(单位:秒)
SMS_CODE_REDIS_EXPIRES = 300   # 短信验证码有效期(单位:秒)
SMS_CODE_FLAG_REDIS_EXPIRES = 300   # 短信验证码有效期(单位:秒)

# 找回密码常量数据
VERIFY_CODE_ERROR = 400   # 验证码有误
USER_MOBILE_ERROR = 404   # 用户名或手机号有误
# SMS_CODE_EXPIRED = 410   # 验证码已过期
ACCESS_TOKEN__REDIS_EXPIRES = 600   # access_token有效期