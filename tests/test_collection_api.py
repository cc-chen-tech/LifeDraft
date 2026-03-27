"""Collection API E2E测试脚本

自动测试收集系统的所有新API端点

注意：这是一个独立的 E2E 测试脚本，需要手动运行：
    python tests/test_collection_api.py

不会被 pytest 自动收集（测试函数使用 _test_ 前缀）。
"""

import sys

import requests

BASE_URL = "http://localhost:8000/api"


# 创建一个测试用户
def create_test_user():
    """创建测试用户或返回现有用户"""
    # 尝试注册新用户
    register_data = {"display_name": "测试用户"}
    resp = requests.post(f"{BASE_URL}/auth/register", json=register_data)

    if resp.status_code == 200:
        data = resp.json()
        print(f"✅ 创建测试用户成功: {data['user']['public_id']}")
        return data["token"]

    # 如果已存在，尝试登录（使用已知的private_id）
    # 这里简化处理，直接返回None
    print("⚠️  创建用户失败，可能需要手动提供token")
    return None


# 创建测试游戏
def create_test_game(token: str):
    """创建测试游戏"""
    print("\n🎮 创建测试游戏...")

    headers = {"Authorization": f"Bearer {token}"}
    data = {
        "player_name": "测试主角",
        "life_vision": "成为传奇",
        "character_settings": {
            "player_name": "测试主角",
            "age": {"age": 25},
            "gender": "男",
            "era": {"era_name": "现代", "year": 2024},
        },
        "language": "zh",
    }

    resp = requests.post(f"{BASE_URL}/games", json=data, headers=headers)

    if resp.status_code in (200, 201):
        result = resp.json()
        game_id = result.get("game_id")
        print(f"✅ 创建游戏成功: game_id={game_id}")
        return game_id
    else:
        print(f"❌ 创建游戏失败: {resp.status_code} - {resp.text[:200]}")
        return None


# 测试1: 实体识别端点
def _test_recognize_entities(token: str, game_id: int = 1):
    """测试实体识别API"""
    print("\n🧪 测试实体识别API...")

    headers = {"Authorization": f"Bearer {token}"}
    data = {"entity_types": ["item", "character", "landmark"], "min_appearances": 3}

    resp = requests.post(
        f"{BASE_URL}/collection/{game_id}/recognize-entities",
        json=data,
        headers=headers,
    )

    if resp.status_code == 200:
        result = resp.json()
        print(f"✅ 实体识别成功")
        print(f"   - 识别到物品: {len(result.get('items', []))}")
        print(f"   - 识别人物: {len(result.get('characters', []))}")
        print(f"   - 识别地点: {len(result.get('landmarks', []))}")
        return result
    elif resp.status_code == 401:
        print("❌ 未授权，需要有效token")
        return None
    else:
        print(f"⚠️  其他响应: {resp.status_code} - {resp.text[:100]}")
        return None


# 测试2: 手动创建物品
def _test_create_item(token: str, game_id: int = 1):
    """测试手动创建物品API"""
    print("\n🧪 测试手动创建物品API...")

    headers = {"Authorization": f"Bearer {token}"}
    data = {"name": "测试物品", "generate_description": False}

    resp = requests.post(
        f"{BASE_URL}/collection/{game_id}/items/create", json=data, headers=headers
    )

    if resp.status_code == 200:
        result = resp.json()
        print(f"✅ 创建物品成功: {result.get('message')}")
        return True
    elif resp.status_code == 400:
        error = resp.json()
        if "已存在" in error.get("detail", ""):
            print(f"✅ 物品已存在（预期行为）")
            return True
        print(f"❌ 创建失败: {error}")
        return False
    elif resp.status_code == 401:
        print("❌ 未授权")
        return False
    else:
        print(f"⚠️  其他响应: {resp.status_code} - {resp.text[:100]}")
        return False


# 测试3: 获取收集列表
def _test_get_collection(token: str, game_id: int = 1):
    """测试获取收集列表API"""
    print("\n🧪 测试获取收集列表API...")

    headers = {"Authorization": f"Bearer {token}"}

    resp = requests.get(f"{BASE_URL}/collection/{game_id}", headers=headers)

    if resp.status_code == 200:
        result = resp.json()
        print(f"✅ 获取收集列表成功")
        print(f"   - 人物: {result.get('total_characters', 0)}")
        print(f"   - 物品: {result.get('total_items', 0)}")
        print(f"   - 标志物: {result.get('total_landmarks', 0)}")
        return result
    elif resp.status_code == 401:
        print("❌ 未授权")
        return None
    else:
        print(f"⚠️  其他响应: {resp.status_code} - {resp.text[:100]}")
        return None


# 测试4: 删除物品
def _test_delete_item(token: str, game_id: int = 1, item_name: str = "测试物品"):
    """测试删除物品API"""
    print(f"\n🧪 测试删除物品API (物品: {item_name})...")

    headers = {"Authorization": f"Bearer {token}"}

    resp = requests.delete(
        f"{BASE_URL}/collection/{game_id}/items/{item_name}", headers=headers
    )

    if resp.status_code == 200:
        result = resp.json()
        print(f"✅ 删除成功: {result.get('message')}")
        return True
    elif resp.status_code == 404:
        print(f"✅ 物品不存在（可能已被删除）")
        return True
    elif resp.status_code == 401:
        print("❌ 未授权")
        return False
    else:
        print(f"⚠️  其他响应: {resp.status_code} - {resp.text[:100]}")
        return False


# 测试5: 批量添加实体
def _test_add_entities(token: str, game_id: int = 1):
    """测试批量添加实体API"""
    print("\n🧪 测试批量添加实体API...")

    headers = {"Authorization": f"Bearer {token}"}
    data = {
        "items": [
            {
                "name": "测试物品A",
                "description": "这是一个测试物品",
                "category": "tool",
                "importance": "normal",
                "appear_count": 3,
                "appear_contexts": ["第一周", "第三周"],
            }
        ],
        "characters": [],
        "landmarks": [],
    }

    resp = requests.post(
        f"{BASE_URL}/collection/{game_id}/add-entities", json=data, headers=headers
    )

    if resp.status_code == 200:
        result = resp.json()
        print(f"✅ 批量添加成功: {result.get('message')}")
        print(f"   - 添加物品: {result.get('added_items', [])}")
        return True
    elif resp.status_code == 401:
        print("❌ 未授权")
        return False
    else:
        print(f"⚠️  其他响应: {resp.status_code} - {resp.text[:100]}")
        return False


def main():
    print("=" * 60)
    print("Collection API E2E 测试")
    print("=" * 60)

    # 检查后端是否运行
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        if resp.status_code == 200:
            print("✅ 后端服务运行正常")
        else:
            print(f"⚠️  后端响应异常: {resp.status_code}")
    except requests.exceptions.ConnectionError:
        print("❌ 后端服务未运行，请先启动: python run_api.py")
        sys.exit(1)

    # 获取token
    token = create_test_user()

    if not token:
        print("\n请手动提供token来继续测试:")
        print(f"export TEST_TOKEN='your_token_here'")
        print(f"python {sys.argv[0]}")
        sys.exit(1)

    # 创建测试游戏
    game_id = create_test_game(token)
    if not game_id:
        print("❌ 无法创建测试游戏，终止测试")
        sys.exit(1)

    # 运行所有测试
    print("\n" + "=" * 60)
    print("开始API测试")
    print("=" * 60)

    results = []

    # 测试1: 实体识别
    result1 = _test_recognize_entities(token, game_id)
    results.append(("实体识别", result1 is not None))

    # 测试2: 创建物品
    result2 = _test_create_item(token, game_id)
    results.append(("创建物品", result2))

    # 测试3: 获取列表
    result3 = _test_get_collection(token, game_id)
    results.append(("获取列表", result3 is not None))

    # 测试4: 批量添加
    result4 = _test_add_entities(token, game_id)
    results.append(("批量添加", result4))

    # 测试5: 删除物品
    result5 = _test_delete_item(token, game_id, item_name="测试物品A")
    results.append(("删除物品", result5))

    # 测试结果汇总
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    failed = len(results) - passed

    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status}: {name}")

    print(f"\n总计: {passed} 通过, {failed} 失败")

    if failed == 0:
        print("\n🎉 所有测试通过!")
        return 0
    else:
        print("\n⚠️  部分测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
