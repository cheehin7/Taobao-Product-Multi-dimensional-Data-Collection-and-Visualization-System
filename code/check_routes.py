from app import app

print("="*50)
print("Flask 路由检查")
print("="*50)

print("\n可视化相关路由检查:")
for rule in app.url_map.iter_rules():
    if 'visualization' in rule.rule:
        print(f"{rule.rule} -> {rule.endpoint}")

routes = []
for rule in app.url_map.iter_rules():
    routes.append(f"{rule.rule} -> {rule.endpoint}")

# 按字母顺序排序
for route in sorted(routes):
    print(route)

print("="*50)
print(f"共计 {len(routes)} 个路由")
print("="*50) 