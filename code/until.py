import pymysql


def coon():
    con = pymysql.connect(host='127.0.0.1'  # 连接名称，默认127.0.0.1
                          , user='root'  # 用户名
                          , passwd='123456'  # 密码
                          , port=3306  # 端口，默认为3306
                          , db='comment1'  # 数据库名称
                          , charset='utf8mb4'  # 字符编码
                          )
    cur = con.cursor()  # 生成游标对象
    return con, cur


def close():
    con, cur = coon()
    cur.close()
    con.close()


def serch(sql):
    con, cur = coon()
    cur.execute(sql)
    res = cur.fetchall()
    close()
    return res


def insert(sql):
    con, cur = coon()
    cur.execute(sql)
    con.commit()
    close()


def userlogin(username, password):
    sql = 'select id,password from users where username = "{0}"'.format(username)
    res = serch(sql)
    if res == ():
        data = {
            'code': 201,
            'msg': '用户未注册'
        }
        return data
    else:
        if res[0][1] == password:
            data = {
                'code': 200,
                'msg': '登录成功',
                'userid': res[0][0]
            }
            return data
        else:
            data = {
                'code': 200,
                'msg': '用户名密码错误',
                'userid': res[0][0]
            }
            return data


def singup(username, password):
    sql = 'select id from users where username = "{0}"'.format(username)
    res = serch(sql)
    if res == ():
        sql = 'insert into users(username,password) values("%s","%s")' % (
            username, password
        )
        insert(sql)
        data = {
            'msg': "注册成功"
        }
        return data
    else:
        data = {
            'msg': "当前用户名已经注册，请勿重复注册"
        }
        return data
