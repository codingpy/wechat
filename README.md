# wechat

WeChat - Free messaging and calling app

Usage:

```python
import wechat

wechat.login()  # Scan to log in

msgs = wechat.init()
next(msgs)

wechat.send('hello, world', to='filehelper')
```
