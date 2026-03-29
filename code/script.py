import random

import requests
import re, json
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


def main():
    for i in range(0, 20):    #每页10条评论，设置爬取20页
        cookies = {
            'shshshfpa': '99c4ebce-91a3-1624-765f-e3a178d687a0-1676660884',
            'shshshfpb': 'e4aeDPkF22IlabydcZH287w',
            'areaId': '24',
            'ipLoc-djd': '24-2144-3909-58335',
            'JSESSIONID': '01BF65645C666A821CA6DADB022538FF.s1',
            'jwotest_product': '99',
        }

        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
            'Cache-Control': 'max-age=0',
            'Connection': 'keep-alive',

            # 'Cookie': 'shshshfpa=f1c4bdd6-a40a-eb82-ba34-65fbb4c3d6c2-1655453381; shshshfpb=hI5q1zt5yJrz6_hJKZ270Mw; __jdu=16554533795131453259026; pinId=3Q1Ua7nZ3SdfgpuN3UCfc7V9-x-f3wj7; shshshfpx=f1c4bdd6-a40a-eb82-ba34-65fbb4c3d6c2-1655453381; pin=jd_5eeec9d432d28; unick=lhz%E5%86%8D%E5%9B%9E%E9%A6%96; _tp=lnSv803HYKt%2BnLEgC%2BdKQkl4W2474R5oVqzcIj1TTLQ%3D; _pst=jd_5eeec9d432d28; areaId=19; PCSYCityID=CN_440000_440600_0; ipLoc-djd=19-1666-36264-59522; unpl=JF8EAMpnNSttWx8GBhJXThRHGQhUW1gIGEcGOmNXUFtRTFECEgZPRRF7XlVdXxRKFR9sYhRUVFNIVQ4bAisSEXteXVdZDEsWC2tXVgQFDQ8VXURJQlZAFDNVCV9dSRZRZjJWBFtdT1xWSAYYRRMfDlAKDlhCR1FpMjVkXlh7VAQrAhwWFE5ZVlxbAE8XAW9iAVZeXENVBhwyGiIXe21kXl8BShQGX2Y1VW0aHwgCEwsSFhQGXVNaWQ1PFQFpbwFUX1hOUAcYBhMTE0xtVW5e; __jdv=76161171|baidu-pinzhuan|t_288551095_baidupinzhuan|cpc|0f3d30c8dba7459bb52f2eb5eba8ac7d_0_2ec28dd7fcd1441ba4d5c57864685ef0|1679653153917; __jda=122270672.16554533795131453259026.1655453379.1679640317.1679653154.65; __jdc=122270672; jsavif=0; shshshfp=4fe9e4e357943fc5c8c67a644113a1f5; wlfstk_smdl=uv1n0w6ltsbjoy848yvvuwbajsarp6gj; 3AB9D23F7A4B3C9B=XF5QFBJG4XAYXF7DOFM7KA4ZM6CCBGUEVEW3SX2C7DLKMNO5Z73A6S3XKKN3C7L3YASCTRJXQXMZQGI3KAIYLMQO5A; TrackID=1_oul2wCD8wPll9c0GHgRnxwnvZTtKAB7gvxbd9fe1Ybb8B7l82d8qH_OXfR_0zRNyFvfKsXjNDcqWU_otIq7xNjxtYSBsv0f2RTzN2iAtv5BpXg4bABL-Wi7vQ-Nj-46CkAj--J0J1N1KWY88iO3-g; thor=565FFBA6353AD0AE8604FFC270A9221F02F406A3958BA9CED477388F92ED614EDA2D5ABDD0EE0101871DA55FFCB9F7CF804A46643EF61543D08022ED303529AC84EFDDE34DE579D6295EB7FEAAB97F8A51662E7E95BC8CCA51DE8F73EAF26E8B9D6CBBC3EF23FFA461D519254B638AE5289BB271CE413ED75AACAB1479C21CE83245E2E0FC433E9C50FF23E94065E1414998A5FC0F48C7A04BD90F7B093AEACF; ceshi3.com=201; token=bf06aa3aefcf9d0f1e5f105d46ec6b13,3,933141; CA1AN5BV0CA8DS2EPC=76021f96b4713622ddfb888ec643df8a; PCA9D23F7A4B3CSS=c4a0cee710b38322f128a0cd25b975ce; __tk=a50d1264bb684d9d71b6349ba47f3538,3,933141; _gia_d=1; 3AB9D23F7A4B3CSS=jdd03XF5QFBJG4XAYXF7DOFM7KA4ZM6CCBGUEVEW3SX2C7DLKMNO5Z73A6S3XKKN3C7L3YASCTRJXQXMZQGI3KAIYLMQO5AAAAAMHCMWC4TYAAAAAC4TVEFCKL42QEYX; shshshsID=676c97e1f594c1deaa6b45ef86250e4c_23_1679653831156; __jdb=122270672.25.16554533795131453259026|65.1679653154',


            # 'Cookie': 'shshshfpa=99c4ebce-91a3-1624-765f-e3a178d687a0-1676660884; shshshfpb=e4aeDPkF22IlabydcZH287w; areaId=24; ipLoc-djd=24-2144-3909-58335; JSESSIONID=01BF65645C666A821CA6DADB022538FF.s1; jwotest_product=99',

            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36 Edg/110.0.1587.56',
            'sec-ch-ua': '"Chromium";v="110", "Not A(Brand";v="24", "Microsoft Edge";v="110"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
        }

        params = {
            'callback': 'fetchJSON_comment98',
            'productId': '10066185480208',     #这里是需要爬取的商品评论京东ID，想爬取其他商品就换这个id,在网页上有商品的这个id

                # 参考商品ID：     10028600516824  100027789689,100030284404, 10042347428853, 100041239020, 100035246702, 100020062339,
                #  100039786535, 100021353921, 100044834013, 100051278473, 100023150129, 100035246614, 10061777921310,
                #  10022266469383, 10022824744668, 100052930269, 10024480172096, 10043008899161, 10023459005420, 10068813996297

        'score': '0',
            'sortType': '5',
            'page': i,
            'pageSize': '10',
            'isShadowSku': '0',
            'fold': '1',
        }

        response = requests.get('https://club.jd.com/comment/productPageComments.action', params=params,
                                cookies=cookies,
                                headers=headers).text
        jsonObj = json.loads(re.match("(fetchJSON_comment98\()(.*)(\);)", response).group(2))

        for comment in jsonObj["comments"]:
            nickname = comment["nickname"]
            score = comment["score"]
            content = comment["content"]
            productColor = comment["productColor"]
            try:
                imageCount = comment['imageCount']
            except:
                imageCount = random.randint(1, 9)
            print(nickname,score,content,productColor)
            sql = 'insert into data(nickname,score,content,productColor,imageCount) values("%s","%s","%s","%s","%s")' % (
                nickname, score, content, productColor, imageCount
            )
            insert(sql)


main()
