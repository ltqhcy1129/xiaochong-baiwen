"""异宠图鉴：物种图文档案。

分两份数据：
  SPECIES   可以养的（外来种或人工繁育成熟，法律上个人可持有）
  FORBIDDEN 不能养的（国家重点保护野生动物、CITES 附录物种、需专用标识的）

legal 字段只用在 SPECIES 上：
  free  个人可养，无额外手续
  doc   可养，但要合法来源凭证或专用标识（条目里会写清楚）

法规口径以《国家重点保护野生动物名录》（2021）、《濒危野生动植物种国际贸易公约》
附录及核准文件、《野生动物保护法》、《外来入侵物种管理办法》为准。
各省市可能有更严的地方名录，落地时以当地林业和草原 / 农业农村主管部门答复为准。

图片不在这里：由 tools/fetch_dex_img.py 预抓，存 static/dex/<k>.jpg，运行时不联网。
"""

# level: 1 新手可养 / 2 需要做功课 / 3 进阶，不建议第一次养
# temp/hum: 成体常规饲养区间，热点温度只作参考
SPECIES = [
    # ---------- 守宫 ----------
    {
        "k": "leopard-gecko", "name": "豹纹守宫", "group": "守宫",
        "latin": "Eublepharis macularius", "en": "Leopard Gecko",
        "alias": ["豹守", "豹纹"], "size": "成体 18–25 cm", "life": "10–15 年",
        "level": 1, "temper": "温顺，接受上手", "temp": [28, 32], "hum": [40, 60],
        "feed": "幼体隔天，成体 5–7 天一次，活饵为主",
        "shed": "3–5 周一次，幼体更频繁",
        "tip": "必须给加热垫 + 温控，靠腹部温度消化；不能只靠晒灯。",
        "ill": ["蜕皮不全（脚趾、尾尖）", "缺钙性软骨病 MBD", "肠炎"],
        "no": "幼体不要用沙子，误食会肠梗阻",
        "legal": "free"
    },
    {
        "k": "crested-gecko", "name": "睫角守宫", "group": "守宫",
        "latin": "Correlophus ciliatus", "en": "Crested Gecko",
        "alias": ["睫角"], "size": "成体 20–25 cm（含尾）", "life": "15–20 年",
        "level": 1, "temper": "活跃，跳跃，少上手", "temp": [22, 26], "hum": [60, 80],
        "feed": "果泥隔天 + 每周 1–2 次蟋蟀",
        "shed": "4–6 周一次",
        "tip": "怕热不怕冷，超过 28℃ 就要降温，很多新手是热死的不是冻死的。",
        "ill": ["尾部蜕皮不全", "缺钙", "脱水"],
        "no": "不要长期高于 28℃，不要用加热灯直烤",
        "legal": "free"
    },
    {
        "k": "african-fat-tail", "name": "肥尾守宫", "group": "守宫",
        "latin": "Hemitheconyx caudicinctus", "en": "African Fat-Tailed Gecko",
        "alias": ["肥尾"], "size": "成体 18–23 cm", "life": "10–15 年",
        "level": 1, "temper": "温顺，比豹纹更胆小", "temp": [28, 32], "hum": [50, 70],
        "feed": "成体 5–7 天一次", "shed": "3–5 周一次",
        "tip": "湿度比豹纹高，需要湿躲避；尾粗是健康标志，断尾后难再生。",
        "ill": ["蜕皮不全", "拒食", "缺钙"],
        "no": "不要与豹纹混养",
        "legal": "free"
    },
    {
        "k": "gargoyle-gecko", "name": "石像鬼守宫", "group": "守宫",
        "latin": "Rhacodactylus auriculatus", "en": "Gargoyle Gecko",
        "alias": ["石像鬼"], "size": "成体 20–23 cm", "life": "15 年",
        "level": 2, "temper": "温顺，夜行", "temp": [22, 26], "hum": [60, 80],
        "feed": "果泥为主，每周加 1–2 次昆虫", "shed": "4–6 周一次",
        "tip": "和睫角养法接近，但更耐干燥一点；断尾可再生。",
        "ill": ["蜕皮不全", "脱水", "缺钙"],
        "no": "不要高温饲养",
        "legal": "free"
    },
    {
        "k": "leachianus-gecko", "name": "巨人守宫", "group": "守宫",
        "latin": "Rhacodactylus leachianus", "en": "New Caledonian Giant Gecko",
        "alias": ["巨人"], "size": "成体 30–40 cm", "life": "20 年以上",
        "level": 3, "temper": "独居，有领地性", "temp": [22, 26], "hum": [65, 85],
        "feed": "果泥 + 昆虫，成体 3–4 天一次", "shed": "4–8 周一次",
        "tip": "体型最大的守宫，箱体要够大；咬合力强，抓取要稳。",
        "ill": ["肥胖", "蜕皮不全", "脱水"],
        "no": "不要两只成体同箱",
        "legal": "free"
    },
    {
        "k": "pictus-gecko", "name": "豹猫守宫", "group": "守宫",
        "latin": "Paroedura picta", "en": "Madagascar Ground Gecko",
        "alias": ["豹猫", "地守宫"], "size": "成体 15–20 cm（含尾）", "life": "10–15 年",
        "level": 1, "temper": "活跃，跑得快", "temp": [28, 32], "hum": [50, 70],
        "feed": "幼体每天小蟋蟀，成体 3–4 天一次",
        "shed": "3–4 周一次",
        "tip": "地栖，需要 5 cm 以上垫材给它挖；繁殖容易，别随便混养导致爆缸。",
        "ill": ["蜕皮不全", "缺钙", "脱水"],
        "no": "不要用光滑底板，它会一直打滑",
        "legal": "free"
    },
    {
        "k": "madagascar-day-gecko", "name": "马达加斯加日守宫", "group": "守宫",
        "latin": "Phelsuma grandis", "en": "Madagascar Giant Day Gecko",
        "alias": ["日守宫", "马达日守", "马达加斯加日行守宫"], "size": "成体 22–30 cm", "life": "10–15 年",
        "level": 2, "temper": "日行，胆小易断尾", "temp": [26, 30], "hum": [60, 80],
        "feed": "果泥 + 昆虫，隔天一次",
        "shed": "4–6 周一次",
        "tip": "少数白天活动的守宫，必须给 UVB；皮肤极薄，抓一次就可能撕伤。",
        "ill": ["缺钙", "脱水", "皮肤撕裂"],
        "no": "不要徒手抓，不要用网兜捞",
        "legal": "free"
    },
    {
        "k": "golden-gecko", "name": "金守宫", "group": "守宫",
        "latin": "Chondrodactylus bibronii", "en": "Bibron's Thick-toed Gecko",
        "alias": ["比氏守宫"], "size": "成体 15–20 cm", "life": "10–15 年",
        "level": 2, "temper": "夜行，动作快", "temp": [28, 32], "hum": [40, 60],
        "feed": "5–7 天一次昆虫", "shed": "3–5 周一次",
        "tip": "南非岩栖种，要垂直岩板而不是树皮；比豹纹更耐干，但怕闷。",
        "ill": ["蜕皮不全", "缺钙", "呼吸道感染"],
        "no": "不要长期高湿，不要用纯树栖箱",
        "legal": "free"
    },
    {
        "k": "western-banded-gecko", "name": "西部带纹守宫", "group": "守宫",
        "latin": "Coleonyx variegatus", "en": "Western Banded Gecko",
        "alias": ["带纹守宫"], "size": "成体 12–15 cm", "life": "8–12 年",
        "level": 1, "temper": "胆小，夜行", "temp": [28, 32], "hum": [40, 55],
        "feed": "3–5 天一次小昆虫", "shed": "3–5 周一次",
        "tip": "北美沙漠种，耐干不耐湿；体型小，缝隙要堵严，容易越狱。",
        "ill": ["脱水", "蜕皮不全", "应激拒食"],
        "no": "不要高湿饲养，不要与大个体混养",
        "legal": "free"
    },
    {
        "k": "knob-tailed-gecko", "name": "瘤尾守宫", "group": "守宫",
        "latin": "Nephrurus levis", "en": "Smooth Knob-Tailed Gecko",
        "alias": ["瘤尾"], "size": "成体 12–15 cm（含尾）", "life": "10–15 年",
        "level": 3, "temper": "胆小，夜间巡游", "temp": [26, 30], "hum": [40, 55],
        "feed": "4–6 天一次昆虫", "shed": "3–4 周一次",
        "tip": "尾端是个肉质小球，受惊会整条甩断且极难再生——抓的时候托住身体别碰尾。",
        "ill": ["断尾不愈", "脱水", "应激拒食"],
        "no": "绝对不要拎尾巴",
        "legal": "free"
    },

    # ---------- 蜥蜴 ----------
    {
        "k": "bearded-dragon", "name": "鬃狮蜥", "group": "蜥蜴",
        "latin": "Pogona vitticeps", "en": "Central Bearded Dragon",
        "alias": ["鬃狮"], "size": "成体 40–60 cm", "life": "8–12 年",
        "level": 1, "temper": "温顺，互动性强", "temp": [30, 35], "hum": [40, 50],
        "feed": "幼体每天 2 次昆虫，成体隔天 + 蔬菜",
        "shed": "4–8 周一次，幼体更频繁",
        "tip": "必须 UVB，否则缺钙瘫软；热点要能到 38℃，冷区留 28℃。",
        "ill": ["MBD 缺钙", "肠胃停滞", "尾部蜕皮不全"],
        "no": "不要用钙沙，不要无 UVB 长期养",
        "legal": "free"
    },
    {
        "k": "blue-tongue", "name": "蓝舌石龙子", "group": "蜥蜴",
        "latin": "Tiliqua scincoides", "en": "Blue-tongued Skink",
        "alias": ["蓝舌"], "size": "成体 45–60 cm", "life": "15–20 年",
        "level": 2, "temper": "温顺，行动慢", "temp": [28, 32], "hum": [50, 70],
        "feed": "杂食：狗粮/猫粮 + 蔬果 + 少量昆虫，隔天一次",
        "shed": "4–6 周一次",
        "tip": "杂食容易喂错，蔬菜占比要够；缺钙很常见。",
        "ill": ["肥胖", "缺钙", "口腔炎"],
        "no": "不要只喂昆虫或只喂肉",
        "legal": "free"
    },
    {
        "k": "australian-water-dragon", "name": "澳洲水龙", "group": "蜥蜴",
        "latin": "Intellagama lesueurii", "en": "Australian Water Dragon",
        "alias": ["水龙"], "size": "成体 60–90 cm", "life": "10–15 年",
        "level": 2, "temper": "警觉，熟悉后较稳", "temp": [28, 33], "hum": [60, 80],
        "feed": "昆虫 + 蔬果 + 少量鱼虾，每天或隔天",
        "shed": "4–6 周一次",
        "tip": "半水栖，必须给能整只泡进去的水盆，且水要每天换；不给水会脱水。",
        "ill": ["脱水", "MBD", "尾部感染"],
        "no": "不要纯陆养，不要用浅碟当水盆",
        "legal": "free"
    },
    {
        "k": "green-basilisk", "name": "绿双冠蜥", "group": "蜥蜴",
        "latin": "Basiliscus plumifrons", "en": "Green Basilisk",
        "alias": ["双冠蜥", "耶稣蜥"], "size": "成体 60–75 cm", "life": "8–10 年",
        "level": 2, "temper": "神经质，跑得极快", "temp": [28, 32], "hum": [70, 85],
        "feed": "昆虫 + 蔬果，每天",
        "shed": "4–6 周一次",
        "tip": "受惊会直接冲进水里、还能踩水跑，箱体必须有盖且水面够大。",
        "ill": ["应激脱水", "MBD", "吻端擦伤"],
        "no": "不要用敞口箱，玻璃反射会让它一直撞",
        "legal": "free"
    },
    {
        "k": "frilled-dragon", "name": "褶伞蜥", "group": "蜥蜴",
        "latin": "Chlamydosaurus kingii", "en": "Frilled Lizard",
        "alias": ["伞蜥"], "size": "成体 70–90 cm", "life": "10–15 年",
        "level": 3, "temper": "紧张时开伞张嘴", "temp": [28, 33], "hum": [50, 70],
        "feed": "昆虫为主 + 少量蔬果，隔天",
        "shed": "4–8 周一次",
        "tip": "纯树栖，需要 1.2 m 以上的高箱和大量竖枝；长期小箱会撞伤吻部。",
        "ill": ["吻部擦伤", "应激拒食", "MBD"],
        "no": "不要用矮箱，不要频繁搬动",
        "legal": "free"
    },
    {
        "k": "desert-iguana", "name": "沙漠鬣蜥", "group": "蜥蜴",
        "latin": "Dipsosaurus dorsalis", "en": "Desert Iguana",
        "alias": ["沙漠蜥"], "size": "成体 30–40 cm", "life": "10–15 年",
        "level": 2, "temper": "温顺，日行", "temp": [32, 38], "hum": [20, 40],
        "feed": "严格植食：深色叶菜 + 少量花，每天",
        "shed": "4–6 周一次",
        "tip": "需要极高的晒点温度（40℃ 上下），普通爬箱达不到；怕潮不怕干。",
        "ill": ["肠胃停滞", "脱水", "MBD"],
        "no": "不要喂昆虫和蛋白，不要高湿",
        "legal": "free"
    },
    {
        "k": "shingleback", "name": "松果蜥", "group": "蜥蜴",
        "latin": "Tiliqua rugosa", "en": "Shingleback Skink",
        "alias": ["松果", "刺尾石龙子"], "size": "成体 30–40 cm", "life": "15–20 年",
        "level": 2, "temper": "极慢，温顺", "temp": [26, 30], "hum": [40, 60],
        "feed": "杂食：蔬果 + 罐头 + 少量昆虫，隔天一次",
        "shed": "4–8 周一次，鳞片成片掉",
        "tip": "尾巴长得像第二个头，是它的防御；成对养反而更稳。",
        "ill": ["肥胖", "缺钙", "口腔炎"],
        "no": "不要高蛋白催长，会肥胖到脱肛",
        "legal": "free"
    },
    {
        "k": "five-lined-skink", "name": "五线石龙子", "group": "蜥蜴",
        "latin": "Plestiodon fasciatus", "en": "Five-lined Skink",
        "alias": ["蓝尾石龙子"], "size": "成体 12–20 cm", "life": "5–8 年",
        "level": 1, "temper": "胆小，动作快", "temp": [26, 30], "hum": [60, 75],
        "feed": "小昆虫，每天或隔天",
        "shed": "3–4 周一次",
        "tip": "幼体是亮蓝色尾巴，长大就褪成褐色；受惊极易断尾，别拎尾巴。",
        "ill": ["断尾", "脱水", "缺钙"],
        "no": "不要徒手抓尾，不要与成体混养",
        "legal": "free"
    },
    # ---------- 蛇 ----------
    {
        "k": "corn-snake", "name": "玉米蛇", "group": "蛇",
        "latin": "Pantherophis guttatus", "en": "Corn Snake",
        "alias": ["玉米"], "size": "成体 100–150 cm", "life": "15–20 年",
        "level": 1, "temper": "温顺，适合第一条蛇", "temp": [26, 30], "hum": [50, 60],
        "feed": "幼体 5–7 天一只乳鼠，成体 10–14 天",
        "shed": "4–8 周一次",
        "tip": "蜕皮前会蒙眼发白、拒食，是正常的，别急着喂。",
        "ill": ["蜕皮不全", "拒食", "口腔炎"],
        "no": "蜕皮期不要喂食、不要上手",
        "legal": "free"
    },
    {
        "k": "ball-python", "name": "球蟒", "group": "蛇",
        "latin": "Python regius", "en": "Ball Python",
        "alias": ["球蟒"], "size": "成体 90–150 cm", "life": "20–30 年",
        "level": 2, "temper": "胆小，会蜷成球", "temp": [30, 32], "hum": [55, 70],
        "feed": "7–14 天一只，按体重选鼠",
        "shed": "4–8 周一次",
        "tip": "拒食是常态，先查温度、湿度、是否蒙眼，别反复折腾。",
        "ill": ["拒食", "呼吸道感染", "蜕皮不全"],
        "no": "不要频繁换环境，不要上手后立刻喂",
        "legal": "doc"
    },
    {
        "k": "california-kingsnake", "name": "加州王蛇", "group": "蛇",
        "latin": "Lampropeltis californiae", "en": "California Kingsnake",
        "alias": ["王蛇"], "size": "成体 90–120 cm", "life": "15–20 年",
        "level": 1, "temper": "活跃，贪吃", "temp": [26, 30], "hum": [40, 60],
        "feed": "5–10 天一只", "shed": "4–6 周一次",
        "tip": "会吃同类的蛇，必须单养；越狱能力强，箱盖要扣死。",
        "ill": ["肥胖", "蜕皮不全", "口腔炎"],
        "no": "绝对不要与其他蛇同箱",
        "legal": "free"
    },
    {
        "k": "rosy-boa", "name": "玫瑰沙蚺", "group": "蛇",
        "latin": "Lichanura trivirgata", "en": "Rosy Boa",
        "alias": ["玫瑰蟒", "沙蚺"], "size": "成体 90–110 cm", "life": "20–30 年",
        "level": 1, "temper": "温顺、行动慢、好上手", "temp": [28, 31], "hum": [30, 50],
        "feed": "幼体 7–10 天一次，成体 10–14 天一次",
        "shed": "4–6 周一次",
        "tip": "北美小型蚺，耐旱、耐温差，比球蟒更不容易拒食；但它怕闷，垫材保持干燥，只给一个湿躲避。",
        "ill": ["蜕皮不全", "口腔炎", "拒食"],
        "no": "不要长期高湿，不要用大号饲养箱（会缺乏安全感）",
        "legal": "free"
    },
    {
        "k": "hognose", "name": "西部猪鼻蛇", "group": "蛇",
        "latin": "Heterodon nasicus", "en": "Western Hognose",
        "alias": ["猪鼻", "猪鼻蛇"], "size": "成体 45–90 cm", "life": "15–20 年",
        "level": 2, "temper": "爱装死，后沟牙微毒", "temp": [28, 30], "hum": [40, 60],
        "feed": "5–7 天一只，偏爱两栖类气味",
        "shed": "4–6 周一次",
        "tip": "拒食常见，可试蛙味诱食；被咬一般只是局部肿，过敏体质要当心。",
        "ill": ["拒食", "蜕皮不全", "误吞垫材"],
        "no": "不要用颗粒垫材，不要强行填食",
        "legal": "free"
    },
    {
        "k": "milk-snake", "name": "奶蛇", "group": "蛇",
        "latin": "Lampropeltis triangulum", "en": "Milk Snake",
        "alias": ["纳尔逊奶蛇", "帕布拉奶蛇"], "size": "成体 60–90 cm", "life": "15–20 年",
        "level": 1, "temper": "温顺，神经质易抖尾", "temp": [26, 30], "hum": [50, 60],
        "feed": "5–7 天一只乳鼠",
        "shed": "4–6 周一次",
        "tip": "花纹越漂亮越容易被误认成毒蛇，出门别随手拎；其实完全无毒。",
        "ill": ["拒食", "蜕皮不全", "口腔炎"],
        "no": "不要与王蛇同箱，会被吃掉",
        "legal": "free"
    },
    {
        "k": "mexican-black-kingsnake", "name": "墨西哥黑王蛇", "group": "蛇",
        "latin": "Lampropeltis getula nigrita", "en": "Mexican Black Kingsnake",
        "alias": ["黑王蛇"], "size": "成体 90–120 cm", "life": "15–20 年",
        "level": 1, "temper": "活跃，食欲强", "temp": [26, 30], "hum": [40, 60],
        "feed": "5–7 天一只", "shed": "4–6 周一次",
        "tip": "通体乌黑，成体后几乎看不出花纹；比加州王蛇更怕热，夏天别超过 30℃。",
        "ill": ["肥胖", "蜕皮不全", "口腔炎"],
        "no": "不要与其他蛇同箱",
        "legal": "free"
    },
    {
        "k": "florida-kingsnake", "name": "佛州王蛇", "group": "蛇",
        "latin": "Lampropeltis floridana", "en": "Florida Kingsnake",
        "alias": ["布鲁克王蛇"], "size": "成体 90–120 cm", "life": "15–20 年",
        "level": 1, "temper": "温顺，吃食积极", "temp": [26, 30], "hum": [50, 65],
        "feed": "5–7 天一只", "shed": "4–6 周一次",
        "tip": "湿度比加州王蛇略高，蜕皮前给个湿躲避就够，别把整箱弄湿。",
        "ill": ["蜕皮不全", "肥胖", "口腔炎"],
        "no": "不要与其他蛇同箱",
        "legal": "free"
    },
    {
        "k": "bull-snake", "name": "牛蛇", "group": "蛇",
        "latin": "Pituophis catenifer sayi", "en": "Bullsnake",
        "alias": ["松林蛇"], "size": "成体 120–180 cm", "life": "15–20 年",
        "level": 2, "temper": "气势足，爱喷气，实际胆小", "temp": [26, 30], "hum": [40, 55],
        "feed": "7–10 天一只，成体可上大鼠",
        "shed": "4–6 周一次",
        "tip": "北美原生种，能长到一米七；开箱先喷气是虚张声势，别因此不敢喂。",
        "ill": ["口腔炎", "蜕皮不全", "肥胖"],
        "no": "不要长期小箱，会撞伤吻端",
        "legal": "free"
    },
    {
        "k": "garter-snake", "name": "束带蛇", "group": "蛇",
        "latin": "Thamnophis sirtalis", "en": "Common Garter Snake",
        "alias": ["袜带蛇"], "size": "成体 50–70 cm", "life": "6–10 年",
        "level": 2, "temper": "活跃，日行，后沟牙微毒", "temp": [24, 28], "hum": [50, 70],
        "feed": "小鱼、蚯蚓、蛙，3–4 天一次",
        "shed": "3–5 周一次",
        "tip": "少数可以群养的蛇，但要给足空间和躲避；只喂鼠会营养不良。",
        "ill": ["营养不良", "蜕皮不全", "寄生虫"],
        "no": "不要只喂乳鼠，不要与体型差太多的混养",
        "legal": "free"
    },

    # ---------- 龟 ----------
    {
        "k": "chinese-pond-turtle", "name": "中华草龟", "group": "龟",
        "latin": "Mauremys reevesii", "en": "Chinese Pond Turtle",
        "alias": ["乌龟", "草龟"], "size": "成体 15–25 cm", "life": "30 年以上",
        "level": 1, "temper": "温顺，胆小", "temp": [25, 28], "hum": [0, 0],
        "feed": "每天或隔天，龟粮为主", "shed": "盾片逐步脱落",
        "tip": "本土物种，野外种群受保护，只能买人工繁育有来源的个体，别买野捕的。",
        "ill": ["腐皮", "白眼", "肺炎"],
        "no": "不要买来源不明的野捕个体，不要直接换温差大的自来水",
        "legal": "doc"
    },
    {
        "k": "musk-turtle", "name": "密西西比麝香龟", "group": "龟",
        "latin": "Sternotherus odoratus", "en": "Common Musk Turtle",
        "alias": ["小臭蛋", "麝香龟"], "size": "成体 8–12 cm", "life": "20–30 年",
        "level": 1, "temper": "胆小，爱躲", "temp": [24, 28], "hum": [0, 0],
        "feed": "每天少量，龟粮 + 螺 + 虾",
        "shed": "盾片逐步脱落",
        "tip": "底栖龟，水深不用太深但要给攀爬物；受惊会放气味，属正常防御。",
        "ill": ["腐甲", "白眼", "肥胖"],
        "no": "不要用尖锐底砂，会划伤腹甲",
        "legal": "free"
    },
    {
        "k": "razorback-musk", "name": "剃刀麝香龟", "group": "龟",
        "latin": "Sternotherus carinatus", "en": "Razor-backed Musk Turtle",
        "alias": ["剃刀龟"], "size": "成体 10–15 cm", "life": "20–30 年",
        "level": 1, "temper": "温顺，水性好", "temp": [24, 28], "hum": [0, 0],
        "feed": "每天少量，龟粮 + 小鱼虾",
        "shed": "盾片逐步脱落",
        "tip": "背甲有一道高脊，越养越明显；体型小但活动量大，别用小圆缸。",
        "ill": ["腐甲", "软甲", "白眼"],
        "no": "不要用无过滤的静水，容易腐甲",
        "legal": "free"
    },
    {
        "k": "map-turtle", "name": "地图龟", "group": "龟",
        "latin": "Graptemys pseudogeographica", "en": "False Map Turtle",
        "alias": ["地图"], "size": "成体 15–25 cm", "life": "20–30 年",
        "level": 2, "temper": "警觉，游动快", "temp": [24, 28], "hum": [0, 0],
        "feed": "每天或隔天，龟粮 + 螺 + 昆虫",
        "shed": "盾片逐步脱落",
        "tip": "对水质极敏感，腐甲率比巴西龟高；必须有强过滤和晒背点。",
        "ill": ["腐甲", "白眼", "软甲"],
        "no": "不要用死水养，不要长期不晒背",
        "legal": "free"
    },
    {
        "k": "painted-turtle", "name": "锦龟", "group": "龟",
        "latin": "Chrysemys picta", "en": "Painted Turtle",
        "alias": ["彩龟"], "size": "成体 12–18 cm", "life": "20–30 年",
        "level": 1, "temper": "活泼，爱晒背", "temp": [22, 27], "hum": [0, 0],
        "feed": "每天少量，龟粮 + 水生昆虫",
        "shed": "盾片逐步脱落",
        "tip": "边缘是鲜红色花纹；耐寒不耐热，夏天水温别超过 28℃。",
        "ill": ["腐甲", "白眼", "维生素 A 缺乏"],
        "no": "不要高温养，不要长期室内无日照",
        "legal": "free"
    },
    # ---------- 两栖 ----------
    {
        "k": "pacman-frog", "name": "角蛙", "group": "两栖",
        "latin": "Ceratophrys cranwelli", "en": "Cranwell's Horned Frog",
        "alias": ["钟角蛙", "角蛙"], "size": "成体 8–12 cm", "life": "8–15 年",
        "level": 1, "temper": "静止伏击，会咬手指", "temp": [24, 28], "hum": [70, 85],
        "feed": "幼体 2–3 天，成体 7–10 天，鱼虾/昆虫/乳鼠",
        "shed": "2–4 周一次，会吃掉自己的皮",
        "tip": "只吃活物或晃动的食物，喂太多会撑死；不要天天喂。",
        "ill": ["肠梗阻", "肥胖", "红腿病"],
        "no": "不要用手直接逗，不要与同类合养",
        "legal": "free"
    },
    {
        "k": "red-eyed-tree-frog", "name": "红眼树蛙", "group": "两栖",
        "latin": "Agalychnis callidryas", "en": "Red-eyed Tree Frog",
        "alias": ["红眼"], "size": "成体 5–7 cm", "life": "5–8 年",
        "level": 3, "temper": "夜行，观赏为主", "temp": [24, 28], "hum": [70, 85],
        "feed": "每隔 2–3 天喂蟋蟀（比眼距小）",
        "shed": "2–4 周一次",
        "tip": "对水质和通风极敏感，需要雨林缸 + 每日喷雾。",
        "ill": ["脱水", "细菌感染", "营养不良"],
        "no": "不要用自来水直接喷，不要上手",
        "legal": "free"
    },
    {
        "k": "axolotl", "name": "六角恐龙", "group": "两栖",
        "latin": "Ambystoma mexicanum", "en": "Axolotl",
        "alias": ["六角", "钝口螈"], "size": "成体 20–30 cm", "life": "10–15 年",
        "level": 2, "temper": "温和，行动慢", "temp": [16, 20], "hum": [0, 0],
        "feed": "每天或隔天，蚯蚓/专用饲料",
        "shed": "表皮持续代谢，不集中蜕皮",
        "tip": "怕热，25℃ 以上就开始出问题，夏天必须降温；野外极危，只能买人工繁育个体。",
        "ill": ["真菌感染", "应激掉鳃", "肠炎"],
        "no": "不要和小鱼混养，不要高于 24℃",
        "legal": "doc"
    },
    {
        "k": "whites-tree-frog", "name": "老爷树蛙", "group": "两栖",
        "latin": "Litoria caerulea", "en": "White's Tree Frog",
        "alias": ["白氏树蛙", "老爷"], "size": "成体 8–12 cm", "life": "10–15 年",
        "level": 1, "temper": "温顺，可上手", "temp": [24, 28], "hum": [60, 80],
        "feed": "5–7 天一次蟋蟀/杜比亚",
        "shed": "2–4 周一次，会吃掉自己的皮",
        "tip": "最容易上手的蛙，但会吃任何能塞进嘴的东西，别和小个体混养。",
        "ill": ["肥胖", "脱水", "红腿病"],
        "no": "不要与小鱼小蛙混养，不要长期低于 20℃",
        "legal": "free"
    },
    {
        "k": "african-clawed-frog", "name": "非洲爪蟾", "group": "两栖",
        "latin": "Xenopus laevis", "en": "African Clawed Frog",
        "alias": ["爪蟾", "水蟾"], "size": "成体 10–13 cm", "life": "10–15 年",
        "level": 1, "temper": "完全水栖，活跃", "temp": [20, 25], "hum": [0, 0],
        "feed": "隔天一次，专用沉水饲料/蚯蚓",
        "shed": "2–4 周一次，蜕下的皮会吃掉",
        "tip": "一辈子不出水，缸里不要留任何能卡住它的缝；外来种，严禁放生。",
        "ill": ["真菌感染", "红腿病", "水质中毒"],
        "no": "不要放生，不要与小鱼混养（会被吃光）",
        "legal": "free"
    },
    {
        "k": "tomato-frog", "name": "番茄蛙", "group": "两栖",
        "latin": "Dyscophus guineti", "en": "False Tomato Frog",
        "alias": ["番茄"], "size": "成体 6–10 cm", "life": "6–10 年",
        "level": 2, "temper": "静止，受惊会鼓胀", "temp": [22, 26], "hum": [70, 85],
        "feed": "5–7 天一次昆虫",
        "shed": "2–4 周一次",
        "tip": "受惊会分泌黏性物质，弄到眼睛会刺痛，接触后一定洗手。",
        "ill": ["脱水", "肥胖", "皮肤感染"],
        "no": "不要徒手长时间抓，摸完必须洗手",
        "legal": "free"
    },
    {
        "k": "tiger-salamander", "name": "虎纹钝口螈", "group": "两栖",
        "latin": "Ambystoma tigrinum", "en": "Tiger Salamander",
        "alias": ["虎纹螈"], "size": "成体 20–30 cm", "life": "10–15 年",
        "level": 2, "temper": "温顺，夜行", "temp": [16, 22], "hum": [60, 75],
        "feed": "5–7 天一次蚯蚓/昆虫",
        "shed": "3–5 周一次",
        "tip": "陆栖为主但需要潮湿垫材，怕热不怕冷，夏天是危险期。",
        "ill": ["真菌感染", "脱水", "肠炎"],
        "no": "不要高于 24℃，不要用干垫材",
        "legal": "free"
    },
    {
        "k": "african-bullfrog", "name": "非洲牛箱头蛙", "group": "两栖",
        "latin": "Pyxicephalus adspersus", "en": "African Bullfrog",
        "alias": ["非洲牛蛙", "Pixie Frog"], "size": "成体 15–23 cm", "life": "15–20 年",
        "level": 3, "temper": "凶猛，咬人见血", "temp": [24, 28], "hum": [60, 80],
        "feed": "7–10 天一次，昆虫/鱼/乳鼠",
        "shed": "2–4 周一次",
        "tip": "咬合力能咬破手指，喂食必须用镊子；长得快、吃得多、排泄量大。",
        "ill": ["肥胖", "肠梗阻", "红腿病"],
        "no": "绝对不要徒手喂，不要与任何活物混养",
        "legal": "free"
    },
    # ---------- 节肢 ----------
    {
        "k": "chilean-rose", "name": "智利红玫瑰", "group": "节肢",
        "latin": "Grammostola rosea", "en": "Chilean Rose Tarantula",
        "alias": ["红玫瑰", "智利火玫瑰", "捕鸟蛛"], "size": "足展 12–15 cm", "life": "15–20 年（母）",
        "level": 1, "temper": "温顺，会踢毛", "temp": [25, 28], "hum": [60, 75],
        "feed": "成体 7–14 天一只蟋蟀/杜比亚",
        "shed": "2–6 个月一次，蜕皮期绝食",
        "tip": "蜕皮时不要打扰、不要喂食，湿度要跟上，否则卡皮会死。",
        "ill": ["卡皮", "脱水", "螨虫"],
        "no": "蜕皮期不要动它，不要徒手抓",
        "legal": "free"
    },
    {
        "k": "mexican-redknee", "name": "墨西哥红膝", "group": "节肢",
        "latin": "Brachypelma hamorii", "en": "Mexican Red Knee Tarantula",
        "alias": ["红膝"], "size": "足展 13–16 cm", "life": "20–25 年（母）",
        "level": 1, "temper": "温顺，行动慢", "temp": [25, 28], "hum": [60, 70],
        "feed": "7–10 天一只", "shed": "3–6 个月一次",
        "tip": "生长极慢，幼体到成体要几年；本属列入 CITES 附录 II，买的时候要能出具来源证明。",
        "ill": ["卡皮", "拒食（正常）", "脱水"],
        "no": "不要频繁搬动，蜕皮期断食断水",
        "legal": "doc"
    },
    {
        "k": "emperor-scorpion", "name": "帝王蝎", "group": "节肢",
        "latin": "Pandinus imperator", "en": "Emperor Scorpion",
        "alias": ["帝王"], "size": "成体 15–20 cm", "life": "5–8 年",
        "level": 1, "temper": "温顺，螯大毒弱", "temp": [26, 30], "hum": [60, 75],
        "feed": "7–10 天一只昆虫",
        "shed": "3–6 个月一次",
        "tip": "需要躲避和湿度，长期干燥会蜕皮失败。帝王蝎全属列入 CITES 附录 II，买卖要能出合法来源证明。",
        "ill": ["蜕皮失败", "脱水", "真菌"],
        "no": "不要徒手抓，不要干养，不要无证买卖",
        "legal": "doc"
    },
    {
        "k": "salmon-pink-birdeater", "name": "巴西所罗门食鸟蛛", "group": "节肢",
        "latin": "Lasiodora parahybana", "en": "Salmon Pink Birdeater",
        "alias": ["所罗门"], "size": "足展 20–25 cm", "life": "15–20 年（母）",
        "level": 2, "temper": "体型大，踢毛痒", "temp": [25, 28], "hum": [70, 80],
        "feed": "7–10 天一只，成体可给大杜比亚",
        "shed": "3–5 个月一次",
        "tip": "足展能到二十五厘米，箱子要够大；踢毛弄到皮肤会很痒，别揉眼睛。",
        "ill": ["卡皮", "脱水", "螨虫"],
        "no": "不要贴在脸上看，不要徒手接",
        "legal": "free"
    },
    {
        "k": "curly-hair", "name": "洪都拉斯卷毛", "group": "节肢",
        "latin": "Tliltocatl albopilosus", "en": "Curly Hair Tarantula",
        "alias": ["卷毛"], "size": "足展 13–15 cm", "life": "15–20 年（母）",
        "level": 1, "temper": "温顺，动作慢", "temp": [24, 28], "hum": [65, 75],
        "feed": "7–10 天一只",
        "shed": "3–6 个月一次",
        "tip": "最适合新手的捕鸟蛛之一：耐干、不挑食、性格稳。它属 CITES 附录 II，交易要能出合法来源证明。",
        "ill": ["卡皮", "脱水", "拒食"],
        "no": "蜕皮期不要打扰，不要无证买卖",
        "legal": "doc"
    },
    {
        "k": "pink-toe", "name": "圭亚那粉趾", "group": "节肢",
        "latin": "Avicularia avicularia", "en": "Pink-toe Tarantula",
        "alias": ["粉趾", "粉趾捕鸟蛛"], "size": "足展 11–13 cm", "life": "10–15 年（母）",
        "level": 2, "temper": "温顺但跳跃快", "temp": [24, 28], "hum": [75, 85],
        "feed": "7–10 天一只",
        "shed": "3–5 个月一次",
        "tip": "树栖，必须用竖箱 + 树皮，平放养会一直趴底、蜕皮困难。",
        "ill": ["卡皮", "脱水", "应激"],
        "no": "不要用矮箱，不要频繁开盖",
        "legal": "free"
    },
    {
        "k": "asian-forest-scorpion", "name": "亚洲雨林蝎", "group": "节肢",
        "latin": "Heterometrus spinifer", "en": "Asian Forest Scorpion",
        "alias": ["雨林蝎"], "size": "成体 10–15 cm", "life": "6–10 年",
        "level": 2, "temper": "防御性强，螯力大", "temp": [25, 29], "hum": [70, 85],
        "feed": "7–10 天一只昆虫",
        "shed": "3–6 个月一次",
        "tip": "毒弱但夹一下很疼，尾巴举起来是警告不是要蜇；垫材要能挖洞。",
        "ill": ["蜕皮失败", "真菌", "脱水"],
        "no": "不要徒手上手把玩，不要干养",
        "legal": "free"
    },
    {
        "k": "giant-millipede", "name": "非洲巨马陆", "group": "节肢",
        "latin": "Archispirostreptus gigas", "en": "Giant African Millipede",
        "alias": ["巨马陆"], "size": "成体 25–30 cm", "life": "5–10 年",
        "level": 1, "temper": "极温顺，缓慢", "temp": [22, 26], "hum": [70, 85],
        "feed": "腐叶土 + 蔬果 + 钙粉，持续供应",
        "shed": "2–4 个月一次",
        "tip": "吃腐殖质，垫材就是它的食物；受惊会分泌刺激性液体，摸完洗手。",
        "ill": ["脱水", "蜕皮失败", "垫材霉变"],
        "no": "不要用干土，不要让液体进眼睛",
        "legal": "free"
    },
    {
        "k": "vietnamese-centipede", "name": "越南巨人蜈蚣", "group": "节肢",
        "latin": "Scolopendra subspinipes", "en": "Vietnamese Giant Centipede",
        "alias": ["巨人蜈蚣"], "size": "成体 15–20 cm", "life": "5–10 年",
        "level": 3, "temper": "极快、会咬，毒性明显", "temp": [24, 28], "hum": [70, 85],
        "feed": "7–10 天一只昆虫",
        "shed": "2–4 个月一次",
        "tip": "咬一口能肿好几天，过敏体质有风险；开盖前先看清它在哪，跑出来极难抓回。",
        "ill": ["咬伤", "脱水", "蜕皮失败"],
        "no": "绝对不要徒手，不要用敞开式饲养盒",
        "legal": "free"
    },
    {
        "k": "cobalt-blue", "name": "钴蓝捕鸟蛛", "group": "节肢",
        "latin": "Cyriopagopus lividus", "en": "Cobalt Blue Tarantula",
        "alias": ["钴蓝"], "size": "足展 13–15 cm", "life": "10–15 年（母）",
        "level": 3, "temper": "攻击性强，速度极快", "temp": [26, 30], "hum": [70, 85],
        "feed": "7–10 天一只",
        "shed": "3–5 个月一次",
        "tip": "名义上是宠物，实际只能观赏：开盖就冲，毒性比温顺种强得多。",
        "ill": ["咬伤", "卡皮", "脱水"],
        "no": "不要开盖上手，不要用能轻易顶开的盖子",
        "legal": "free"
    },

    # ---------- 昆虫 ----------
    {
        "k": "orchid-mantis", "name": "兰花螳螂", "group": "昆虫",
        "latin": "Hymenopus coronatus", "en": "Orchid Mantis",
        "alias": ["兰花"], "size": "成体 4–6 cm", "life": "8–12 个月",
        "level": 3, "temper": "伏击，同类相残", "temp": [25, 28], "hum": [70, 85],
        "feed": "果蝇/小蟋蟀，幼体每天",
        "shed": "2–3 周一次，共 6–8 次",
        "tip": "蜕皮需要足够湿度，失败就残废；必须单只饲养。",
        "ill": ["蜕皮失败", "脱水", "同类相食"],
        "no": "绝对不要合养",
        "legal": "free"
    },
    {
        "k": "japanese-rhinoceros-beetle", "name": "独角仙", "group": "昆虫",
        "latin": "Trypoxylus dichotomus", "en": "Japanese Rhinoceros Beetle",
        "alias": ["独角仙"], "size": "成体 4–8 cm", "life": "成虫 2–3 个月",
        "level": 1, "temper": "温顺，可上手", "temp": [22, 26], "hum": [60, 75],
        "feed": "成虫果冻/糖水，2–3 天换一次",
        "shed": "幼虫三次蜕皮后化蛹",
        "tip": "成虫寿命只有几个月，大部分时间在幼虫期，土和温控是关键。",
        "ill": ["幼虫土霉变", "成虫脱水", "蛹期失败"],
        "no": "不要用普通园土，不要频繁翻动幼虫",
        "legal": "free"
    },
    {
        "k": "hissing-cockroach", "name": "马达加斯加发声蟑螂", "group": "昆虫",
        "latin": "Gromphadorhina portentosa", "en": "Madagascar Hissing Cockroach",
        "alias": ["发声蟑螂"], "size": "成体 6–8 cm", "life": "2–5 年",
        "level": 1, "temper": "温顺，行动慢", "temp": [24, 28], "hum": [60, 80],
        "feed": "蔬果 + 狗粮 + 落叶，2–3 天一次",
        "shed": "2–3 个月一次",
        "tip": "不会飞、不会爬光滑面，是最好上手的昆虫宠物；受惊会喷气发声。",
        "ill": ["脱水", "霉菌感染", "螨虫"],
        "no": "不要用湿透的垫材，会发霉",
        "legal": "free"
    },
    {
        "k": "dubia-roach", "name": "杜比亚蟑螂", "group": "昆虫",
        "latin": "Blaptica dubia", "en": "Dubia Roach",
        "alias": ["杜比亚"], "size": "成体 4–5 cm", "life": "1–2 年",
        "level": 1, "temper": "不会爬不会飞", "temp": [26, 30], "hum": [50, 70],
        "feed": "蔬果 + 麦麸，2–3 天一次",
        "shed": "1–2 个月一次",
        "tip": "多数人拿它当饲料，其实单养观察也有意思；关键是控温，冷了不繁殖。",
        "ill": ["脱水", "霉菌", "密度过高互食"],
        "no": "不要低于 20℃，不要喂湿烂的菜叶",
        "legal": "free"
    },
    {
        "k": "rainbow-stag", "name": "彩虹锹甲", "group": "昆虫",
        "latin": "Phalacrognathus muelleri", "en": "Rainbow Stag Beetle",
        "alias": ["彩虹锹"], "size": "成体 4–6 cm", "life": "成虫 1–2 年",
        "level": 2, "temper": "温顺，可上手", "temp": [20, 25], "hum": [60, 75],
        "feed": "成虫果冻，2–3 天换一次",
        "shed": "幼虫三次蜕皮后化蛹",
        "tip": "金属光泽会随角度变色；怕热，夏天超过 28℃ 很快衰亡。",
        "ill": ["高温衰亡", "幼虫土劣化", "蛹期失败"],
        "no": "不要高温闷养，不要用腐烂发臭的土",
        "legal": "free"
    },
    {
        "k": "hercules-beetle", "name": "长戟大兜虫", "group": "昆虫",
        "latin": "Dynastes hercules", "en": "Hercules Beetle",
        "alias": ["长戟", "大兜虫"], "size": "成体 8–17 cm", "life": "成虫 6–12 个月",
        "level": 2, "temper": "温顺，力气大", "temp": [20, 25], "hum": [60, 75],
        "feed": "成虫果冻，2–3 天换一次",
        "shed": "幼虫期约 1.5–2 年，三次蜕皮",
        "tip": "幼虫期能长达两年，得有耐心；成虫只活大半年，别指望长期陪伴。",
        "ill": ["幼虫土劣化", "蛹室塌陷", "成虫脱水"],
        "no": "不要频繁翻土，不要用未发酵的土",
        "legal": "free"
    },
    {
        "k": "indian-stick-insect", "name": "印度竹节虫", "group": "昆虫",
        "latin": "Carausius morosus", "en": "Indian Stick Insect",
        "alias": ["竹节虫"], "size": "成体 8–10 cm", "life": "6–12 个月",
        "level": 1, "temper": "极温顺，几乎不动", "temp": [20, 25], "hum": [60, 80],
        "feed": "常春藤/悬铃木叶，每 2–3 天换新鲜",
        "shed": "3–4 周一次",
        "tip": "几乎全是雌性，孤雌生殖，一只就能繁殖出一箱；卵别乱丢，跑出去算外来种。",
        "ill": ["蜕皮失败", "脱水", "叶片农药中毒"],
        "no": "不要喂没洗过的路边叶，不要随意放生",
        "legal": "free"
    },
    {
        "k": "ghost-mantis", "name": "幽灵螳螂", "group": "昆虫",
        "latin": "Phyllocrania paradoxa", "en": "Ghost Mantis",
        "alias": ["幽灵"], "size": "成体 4–5 cm", "life": "8–12 个月",
        "level": 2, "temper": "安静，拟态枯叶", "temp": [24, 28], "hum": [60, 75],
        "feed": "果蝇/小蟋蟀，2–3 天一次",
        "shed": "3–4 周一次",
        "tip": "可以小群养（密度低时），但蜕皮期互相干扰会残废，新手还是单养稳。",
        "ill": ["蜕皮失败", "脱水", "同类相食"],
        "no": "不要高密度合养，不要喂比它大的猎物",
        "legal": "free"
    },

    # ---------- 鸟 ----------
    {
        "k": "cockatiel", "name": "玄凤鹦鹉", "group": "鸟",
        "latin": "Nymphicus hollandicus", "en": "Cockatiel",
        "alias": ["玄凤", "鸡尾鹦鹉"], "size": "成体 30–33 cm", "life": "15–20 年",
        "level": 1, "temper": "亲人，会吹口哨", "temp": [20, 28], "hum": [40, 60],
        "feed": "滋养丸为主 + 少量种子蔬果，每天",
        "shed": "持续换羽，春秋较集中",
        "tip": "种子粮单一喂会营养不良；需要每天出笼活动。",
        "ill": ["脂肪肝", "拔羽", "缺钙"],
        "no": "不要只喂小米，不要长期关小笼",
        "legal": "free"
    },
    {
        "k": "budgerigar", "name": "虎皮鹦鹉", "group": "鸟",
        "latin": "Melopsittacus undulatus", "en": "Budgerigar",
        "alias": ["虎皮"], "size": "成体 18 cm", "life": "8–12 年",
        "level": 1, "temper": "活泼，群居", "temp": [20, 28], "hum": [40, 60],
        "feed": "滋养丸 + 种子 + 青菜，每天",
        "shed": "持续换羽",
        "tip": "单只会抑郁，最好成对；需要啃咬玩具。",
        "ill": ["脂肪瘤", "疥癣", "缺钙"],
        "no": "不要用圆笼，不要只喂谷物",
        "legal": "free"
    },
    {
        "k": "peach-faced-lovebird", "name": "桃脸牡丹鹦鹉", "group": "鸟",
        "latin": "Agapornis roseicollis", "en": "Peach-faced Lovebird",
        "alias": ["牡丹鹦鹉", "情侣鹦鹉"], "size": "成体 15–17 cm", "life": "15–20 年",
        "level": 1, "temper": "活泼，成对更亲", "temp": [20, 28], "hum": [40, 60],
        "feed": "滋养丸 + 种子 + 蔬果，每天",
        "shed": "持续换羽",
        "tip": "国内允许饲养的是桃脸等少数几种，头类牡丹（费氏牡丹等）属保护物种，买前一定问清学名。",
        "ill": ["脂肪肝", "拔羽", "产蛋卡蛋"],
        "no": "不要买来源不明的头类牡丹，不要单只长期关笼",
        "legal": "free"
    },
    {
        "k": "zebra-finch", "name": "斑胸草雀", "group": "鸟",
        "latin": "Taeniopygia guttata", "en": "Zebra Finch",
        "alias": ["珍珠鸟"], "size": "成体 10–11 cm", "life": "5–8 年",
        "level": 1, "temper": "群居，怕人但很活跃", "temp": [18, 28], "hum": [40, 60],
        "feed": "雀类混合谷 + 青菜 + 钙砂，每天",
        "shed": "持续换羽",
        "tip": "不需要人陪，适合上班族；成对或成群养，单只会应激。",
        "ill": ["产蛋卡蛋", "螨虫", "缺钙"],
        "no": "不要单只养，不要用细铁丝底网伤脚",
        "legal": "free"
    },
    {
        "k": "canary", "name": "金丝雀", "group": "鸟",
        "latin": "Serinus canaria", "en": "Canary",
        "alias": ["芙蓉鸟"], "size": "成体 12–14 cm", "life": "8–12 年",
        "level": 1, "temper": "安静，以鸣叫为主", "temp": [16, 26], "hum": [40, 60],
        "feed": "金丝雀混合谷 + 青菜 + 蛋黄，每天",
        "shed": "每年一次集中换羽",
        "tip": "养它是为了听叫，不是盘；换羽期要补蛋白和色素饲料。",
        "ill": ["换羽不顺", "呼吸道感染", "肥胖"],
        "no": "不要频繁搬动，不要喂单一谷子",
        "legal": "free"
    },
    {
        "k": "japanese-quail", "name": "日本鹌鹑", "group": "鸟",
        "latin": "Coturnix japonica", "en": "Japanese Quail",
        "alias": ["鹌鹑"], "size": "成体 15–20 cm", "life": "2–3 年",
        "level": 1, "temper": "胆小，受惊会撞笼", "temp": [18, 26], "hum": [40, 60],
        "feed": "鹌鹑专用颗粒 + 砂砾，每天",
        "shed": "持续少量换羽",
        "tip": "会飞且起飞极突然，笼顶必须软；产蛋多，母鸟要补钙。",
        "ill": ["撞笼外伤", "缺钙软壳蛋", "球虫"],
        "no": "不要用硬顶笼，不要突然大声惊扰",
        "legal": "free"
    },

    # ---------- 小哺乳 ----------
    {
        "k": "sugar-glider", "name": "蜜袋鼯", "group": "小哺乳",
        "latin": "Petaurus breviceps", "en": "Sugar Glider",
        "alias": ["蜜袋", "小蜜"], "size": "成体 12–15 cm（不含尾）", "life": "10–15 年",
        "level": 3, "temper": "夜行，认主但会咬", "temp": [24, 28], "hum": [50, 60],
        "feed": "专用花蜜粮 + 蛋白 + 蔬果，每天",
        "shed": "少量持续掉毛",
        "tip": "必须成对养，单只会自残；钙磷比错了会瘫。",
        "ill": ["缺钙后肢瘫痪", "自残", "肥胖"],
        "no": "不要单养，不要只喂水果",
        "legal": "free"
    },
    {
        "k": "hedgehog", "name": "四趾刺猬", "group": "小哺乳",
        "latin": "Atelerix albiventris", "en": "African Pygmy Hedgehog",
        "alias": ["刺猬", "非洲迷你刺猬"], "size": "成体 15–20 cm", "life": "4–6 年",
        "level": 2, "temper": "胆小，会竖刺", "temp": [24, 28], "hum": [40, 60],
        "feed": "高蛋白猫粮 + 昆虫，每天",
        "shed": "持续少量掉刺（幼体换刺）",
        "tip": "低于 20℃ 会尝试冬眠，家养冬眠很危险，必须保温。",
        "ill": ["肥胖", "皮肤病", "牙病"],
        "no": "不要让环境低于 20℃，不要抓野生刺猬",
        "legal": "free"
    },
    {
        "k": "chinchilla", "name": "龙猫", "group": "小哺乳",
        "latin": "Chinchilla lanigera", "en": "Chinchilla",
        "alias": ["毛丝鼠"], "size": "成体 25–35 cm", "life": "15–20 年",
        "level": 2, "temper": "夜行，怕热", "temp": [18, 22], "hum": [40, 55],
        "feed": "提摩西草 + 专用粮，每天",
        "shed": "持续掉毛，受惊会掉一撮",
        "tip": "超过 25℃ 会中暑死亡，夏天必须空调；要沙浴不是水洗。",
        "ill": ["中暑", "牙齿过长", "毛球症"],
        "no": "不要水洗，不要高于 25℃",
        "legal": "free"
    },
    {
        "k": "syrian-hamster", "name": "金丝熊", "group": "小哺乳",
        "latin": "Mesocricetus auratus", "en": "Syrian Hamster",
        "alias": ["叙利亚仓鼠"], "size": "成体 13–18 cm", "life": "2–3 年",
        "level": 1, "temper": "独居，夜行", "temp": [20, 24], "hum": [40, 60],
        "feed": "仓鼠粮 + 少量蔬果，每天",
        "shed": "持续少量掉毛",
        "tip": "必须单笼，合笼会打死；笼子底面积比层数重要。",
        "ill": ["湿尾", "颊囊炎", "肿瘤"],
        "no": "绝对不要合笼，不要用棉花垫材",
        "legal": "free"
    },
    {
        "k": "guinea-pig", "name": "荷兰猪", "group": "小哺乳",
        "latin": "Cavia porcellus", "en": "Guinea Pig",
        "alias": ["豚鼠", "天竺鼠"], "size": "成体 20–30 cm", "life": "5–8 年",
        "level": 1, "temper": "温顺，群居", "temp": [18, 24], "hum": [40, 60],
        "feed": "提摩西草无限量 + 维 C 蔬果，每天",
        "shed": "持续掉毛",
        "tip": "自身不能合成维 C，缺了会瘫；必须每天给甜椒/西兰花。",
        "ill": ["坏血病（缺维 C）", "牙齿过长", "脚垫炎"],
        "no": "不要只喂颗粒粮，不要单养",
        "legal": "free"
    },
    {
        "k": "campbells-hamster", "name": "三线仓鼠", "group": "小哺乳",
        "latin": "Phodopus campbelli", "en": "Campbell's Dwarf Hamster",
        "alias": ["加卡利亚", "侏儒仓鼠"], "size": "成体 8–10 cm", "life": "1.5–2 年",
        "level": 1, "temper": "独居，动作快", "temp": [20, 24], "hum": [40, 60],
        "feed": "侏儒仓鼠粮 + 少量蔬果，每天",
        "shed": "持续少量掉毛",
        "tip": "和银狐、布丁是同一物种的不同毛色；必须单笼，合笼会打到死。",
        "ill": ["糖尿病倾向", "湿尾", "颊囊炎"],
        "no": "不要合笼，不要喂人吃的甜食",
        "legal": "free"
    },
    {
        "k": "roborovski-hamster", "name": "罗伯罗夫斯基仓鼠", "group": "小哺乳",
        "latin": "Phodopus roborovskii", "en": "Roborovski Hamster",
        "alias": ["老公公", "沙漠侏儒仓鼠"], "size": "成体 5–7 cm", "life": "2–3 年",
        "level": 2, "temper": "极快，只能看不能盘", "temp": [20, 26], "hum": [30, 50],
        "feed": "侏儒仓鼠粮 + 少量蔬果，每天",
        "shed": "持续少量掉毛",
        "tip": "跑得比手快，基本抓不住，适合观赏；耐干，沙浴比垫材更重要。",
        "ill": ["脱水", "牙齿过长", "肿瘤"],
        "no": "不要用高湿垫材，不要频繁上手抓",
        "legal": "free"
    },
    {
        "k": "fancy-rat", "name": "花枝鼠", "group": "小哺乳",
        "latin": "Rattus norvegicus domestica", "en": "Fancy Rat",
        "alias": ["宠物鼠"], "size": "成体 25–30 cm（含尾）", "life": "2–3 年",
        "level": 1, "temper": "亲人，认人，会舔手", "temp": [20, 26], "hum": [40, 60],
        "feed": "鼠粮 + 少量蔬果蛋白，每天",
        "shed": "持续少量掉毛",
        "tip": "必须至少两只，单养会抑郁；呼吸道感染是头号杀手，垫材粉尘要少。",
        "ill": ["支原体呼吸道感染", "肿瘤", "脓肿"],
        "no": "不要单养，不要用粉尘大的垫材",
        "legal": "free"
    },
    {
        "k": "mongolian-gerbil", "name": "蒙古沙鼠", "group": "小哺乳",
        "latin": "Meriones unguiculatus", "en": "Mongolian Gerbil",
        "alias": ["沙鼠"], "size": "成体 10–14 cm", "life": "3–4 年",
        "level": 1, "temper": "活跃，白天也出来", "temp": [20, 26], "hum": [30, 50],
        "feed": "沙鼠粮 + 少量蔬果，每天",
        "shed": "持续少量掉毛",
        "tip": "耐干不耐湿，几乎不喝水；爱挖洞，垫材要深。",
        "ill": ["癫痫样发作", "牙齿过长", "湿尾"],
        "no": "不要高湿饲养，不要用浅垫材",
        "legal": "free"
    },
    {
        "k": "dwarf-rabbit", "name": "家兔", "group": "小哺乳",
        "latin": "Oryctolagus cuniculus domesticus", "en": "Domestic Rabbit",
        "alias": ["侏儒兔", "垂耳兔", "兔子"], "size": "成体 25–35 cm", "life": "8–12 年",
        "level": 2, "temper": "胆小，需要耐心", "temp": [16, 25], "hum": [40, 60],
        "feed": "提摩西草无限量 + 定量兔粮 + 叶菜，每天",
        "shed": "春秋集中换毛，平时也掉",
        "tip": "草占八成，只喂胡萝卜和兔粮会牙齿过长、肠胃停滞致死。",
        "ill": ["肠胃停滞", "牙齿过长", "脚垫炎"],
        "no": "不要只喂胡萝卜和兔粮，不要拎耳朵",
        "legal": "free"
    },
    {
        "k": "mourning-gecko", "name": "哀鳞守宫", "group": "守宫",
        "latin": "Lepidodactylus lugubris", "en": "Mourning Gecko",
        "alias": ["悲鳞守宫", "瓜氏守宫"], "size": "成体 8–10 cm", "life": "8–10 年",
        "level": 1, "temper": "活泼、爱跳，几乎不咬人", "temp": [24, 28], "hum": [60, 80],
        "feed": "小号蟋蟀、果泥，每周 3–4 次",
        "shed": "2–3 周一次，皮常自己吃掉",
        "tip": "几乎全是雌性，孤雌生殖：一只养久了会自己下蛋，孵出来还是雌性。想养就得接受它会越来越多。",
        "ill": ["缺钙软脚", "蜕皮不畅", "卵滞留"],
        "no": "不要两只以上混养在小箱里，会互相压制；不要断钙粉",
        "legal": "free"
    },
    {
        "k": "uromastyx", "name": "埃及刺尾蜥", "group": "蜥蜴",
        "latin": "Uromastyx aegyptia", "en": "Egyptian Uromastyx",
        "alias": ["刺尾鬣蜥", "大刺尾"], "size": "成体 40–45 cm", "life": "15–20 年",
        "level": 3, "temper": "温顺但胆小，受惊会甩尾", "temp": [35, 45], "hum": [15, 30],
        "feed": "纯素：野草、蒲公英、芝麻菜，偶尔少量扁豆；不加动物蛋白",
        "shed": "整片脱落，不像守宫那样撕皮",
        "tip": "它是沙漠素食者，最怕两件事：湿和肉。湿度上去就烂尾，喂虫喂肉就肝衰竭。热点必须到 45℃ 才肯消化。",
        "ill": ["烂尾", "脱水", "代谢性骨病"],
        "no": "不要喂面包虫和大麦虫，不要喷水，不要用保湿垫材",
        "legal": "doc"
    },
    {
        "k": "green-anole", "name": "绿安乐蜥", "group": "蜥蜴",
        "latin": "Anolis carolinensis", "en": "Green Anole",
        "alias": ["变色蜥", "美国安乐蜥"], "size": "成体 12–20 cm", "life": "5–8 年",
        "level": 2, "temper": "活跃、领地性强，会展示喉扇", "temp": [26, 30], "hum": [60, 75],
        "feed": "小蟋蟀、果蝇，每周 4–5 次",
        "shed": "2–3 周一次",
        "tip": "便宜但不好养：需要高湿加通风，两者很难同时做到。市面上大多是野捕个体，带寄生虫、活不过半年。",
        "ill": ["脱水", "寄生虫", "代谢性骨病"],
        "no": "不要多只混养，不要用封闭小盒养",
        "legal": "free"
    },
    {
        "k": "jeweled-lacerta", "name": "珠宝蜥", "group": "蜥蜴",
        "latin": "Timon lepidus", "en": "Jeweled Lacerta",
        "alias": ["蓝斑蜥蜴", "珍珠蜥"], "size": "成体 30–60 cm", "life": "15 年",
        "level": 3, "temper": "机警、跑得极快，需要耐心驯", "temp": [28, 32], "hum": [40, 60],
        "feed": "蟋蟀、杜比亚、偶尔乳鼠，成体每周 2–3 次",
        "shed": "碎皮脱落",
        "tip": "幼体身上有蓝斑，成年后雄性会变成绿底黑头。要 UVB 和很大的活动空间，小箱养会撞玻璃撞到吻部溃烂。",
        "ill": ["吻部擦伤", "代谢性骨病", "尾断不再生"],
        "no": "不要用小于 90cm 的箱，不要断 UVB",
        "legal": "free"
    },
    {
        "k": "king-ratsnake", "name": "王锦蛇", "group": "蛇",
        "latin": "Elaphe carinata", "en": "King Ratsnake",
        "alias": ["大王蛇", "臭黄颌"], "size": "成体 150–200 cm", "life": "15–20 年",
        "level": 3, "temper": "凶、食量大，受惊会喷臭液", "temp": [26, 29], "hum": [50, 65],
        "feed": "每周一只大小合适的鼠；它也吃别的蛇，不要混养",
        "shed": "4–6 周一次",
        "tip": "国产蛇里最皮实的一种，但脾气也最大——开箱就扑，还会喷臭腺。新手想养国产蛇，先想清楚能不能接受。",
        "ill": ["口腔炎", "蜕皮不全", "寄生虫"],
        "no": "不要徒手抓，不要和其他蛇同箱",
        "legal": "doc"
    },
    {
        "k": "african-house-snake", "name": "非洲屋蛇", "group": "蛇",
        "latin": "Boaedon fuliginosus", "en": "African House Snake",
        "alias": ["屋蛇", "褐屋蛇"], "size": "成体 60–90 cm", "life": "12–15 年",
        "level": 1, "temper": "温顺、胆小，夜行", "temp": [26, 29], "hum": [50, 65],
        "feed": "每周一只大小合适的鼠，幼体 5–7 天一次",
        "shed": "4–6 周一次",
        "tip": "最被低估的入门蛇：体型不大、脾气好、吃得稳、不挑食。缺点是夜行，白天基本看不到它动。",
        "ill": ["拒食", "蜕皮不全", "口腔炎"],
        "no": "不要用过高温度（超过 31℃ 会拒食），不要频繁上手",
        "legal": "free"
    },
    {
        "k": "yellow-pond-turtle", "name": "黄喉拟水龟", "group": "龟",
        "latin": "Mauremys mutica", "en": "Yellow Pond Turtle",
        "alias": ["石金钱龟", "黄喉"], "size": "成体 15–20 cm", "life": "25–30 年",
        "level": 2, "temper": "温和、胆小", "temp": [22, 28], "hum": [0, 0],
        "feed": "龟粮为主，配小鱼虾和少量菜叶，每天或隔天",
        "shed": "背甲片状脱落，不明显",
        "tip": "国产龟里最容易被当成“放生龟”的一种。买之前必须要来源证明，野生个体属于保护动物，放生又会造成杂交污染。",
        "ill": ["腐甲", "白眼病", "肺炎"],
        "no": "不要买来放生，不要长期干养",
        "legal": "doc"
    },
    {
        "k": "african-sideneck", "name": "非洲侧颈龟", "group": "龟",
        "latin": "Pelomedusa subrufa", "en": "African Helmeted Turtle",
        "alias": ["头盔侧颈龟", "非洲盔龟"], "size": "成体 20–25 cm", "life": "20–30 年",
        "level": 1, "temper": "活跃、抢食凶", "temp": [24, 28], "hum": [0, 0],
        "feed": "龟粮、小鱼、昆虫，每天",
        "shed": "背甲片状脱落",
        "tip": "头缩不回壳里，只能侧着脖子贴边——这是侧颈龟科的特征。很皮实，但咬合力大，混养会咬掉别的龟的尾巴。",
        "ill": ["腐甲", "软甲", "肺炎"],
        "no": "不要和小龟混养，不要水质长期浑浊",
        "legal": "free"
    },
    {
        "k": "ornate-horned-frog", "name": "钟角蛙", "group": "两栖",
        "latin": "Ceratophrys ornata", "en": "Ornate Horned Frog",
        "alias": ["阿根廷角蛙", "绿角蛙"], "size": "成体 10–15 cm", "life": "6–10 年",
        "level": 2, "temper": "伏击型，什么都往嘴里塞", "temp": [24, 27], "hum": [70, 85],
        "feed": "成体每周 1–2 只鼠或大蟋蟀；宁少勿多",
        "shed": "2–4 周蜕一次，会吃掉",
        "tip": "看起来呆，实际是嘴。喂多了会胀气脱肛，喂活鱼会寄生虫。手上沾了味道伸进去，它一样咬。",
        "ill": ["胀气", "脱肛", "红腿病"],
        "no": "不要天天喂，不要用手逗，不要和任何活物同箱",
        "legal": "free"
    },
    {
        "k": "waxy-monkey-frog", "name": "蜡白猴树蛙", "group": "两栖",
        "latin": "Phyllomedusa sauvagii", "en": "Waxy Monkey Tree Frog",
        "alias": ["蜡猴树蛙", "猴树蛙"], "size": "成体 7–10 cm", "life": "8–12 年",
        "level": 2, "temper": "慢、温和，白天睡觉", "temp": [26, 29], "hum": [50, 70],
        "feed": "蟋蟀、杜比亚，每周 3 次",
        "shed": "2–3 周一次",
        "tip": "它会给自己涂一层蜡防止水分流失，所以不像别的蛙那样怕干。反而怕闷——高湿不通风会烂皮。",
        "ill": ["细菌感染", "脱水", "肥胖"],
        "no": "不要长时间高湿闷养，不要频繁上手",
        "legal": "free"
    },
    {
        "k": "mexican-fireleg", "name": "墨西哥火脚", "group": "节肢",
        "latin": "Brachypelma boehmei", "en": "Mexican Fireleg Tarantula",
        "alias": ["火脚捕鸟蛛"], "size": "足展 14–16 cm", "life": "20–25 年",
        "level": 2, "temper": "慢、温顺，会踢毛", "temp": [24, 28], "hum": [60, 70],
        "feed": "每周 1 只蟋蟀或杜比亚；蜕皮前停食",
        "shed": "幼体每月，成体一年一次，会翻过来蜕",
        "tip": "火脚和红膝最容易混：火脚整条腿是橘红色，红膝只有关节一圈红。它踢的毛会让人痒好几天，别揉眼睛。长得慢，母的能活二十年。",
        "ill": ["蜕皮失败", "脱水", "螨虫"],
        "no": "不要徒手抓，不要在蜕皮期打扰",
        "legal": "doc"
    },
    {
        "k": "white-striped-flower-beetle", "name": "白条花金龟", "group": "昆虫",
        "latin": "Dicronorhina derbyana", "en": "Derby's Flower Beetle",
        "alias": ["白条绿花金龟", "德里花金龟"], "size": "成体 4–5 cm", "life": "成虫 3–5 个月",
        "level": 2, "temper": "温顺，可上手", "temp": [22, 26], "hum": [60, 70],
        "feed": "成虫吃香蕉、果冻；幼虫吃腐叶土",
        "shed": "幼虫三次蜕皮后化蛹",
        "tip": "很好看，但成虫寿命只有几个月，养它其实是养幼虫。腐叶土发酵不到位会烧死幼虫。",
        "ill": ["幼虫烧土死亡", "羽化畸形", "螨虫"],
        "no": "不要用来路不明的园土，不要把成虫和幼虫混养",
        "legal": "free"
    },
    {
        "k": "society-finch", "name": "十姊妹", "group": "鸟",
        "latin": "Lonchura striata", "en": "Society Finch",
        "alias": ["白腰文鸟", "保姆鸟", "文鸟"], "size": "成体 10–11 cm", "life": "5–8 年",
        "level": 1, "temper": "群居、温和、极好养", "temp": [18, 28], "hum": [40, 60],
        "feed": "混合谷物种子 + 青菜 + 墨鱼骨，每天",
        "shed": "持续换羽，春秋较多",
        "tip": "最便宜的入门鸟，也是最常用的“保姆鸟”——会替别的文鸟孵蛋育雏。但也因此常被单独关小笼，其实它必须成对或成群。",
        "ill": ["啄羽", "卵结", "气囊螨"],
        "no": "不要单只饲养，不要只喂小米",
        "legal": "free"
    },
    {
        "k": "gouldian-finch", "name": "七彩文鸟", "group": "鸟",
        "latin": "Chloebia gouldiae", "en": "Gouldian Finch",
        "alias": ["胡锦鸟", "五彩文鸟", "Erythrura gouldiae"], "size": "成体 12–13 cm", "life": "5–8 年",
        "level": 2, "temper": "安静、怕冷、体质偏弱", "temp": [20, 28], "hum": [40, 60],
        "feed": "细粒种子 + 活食（小面包虫、果蝇）+ 墨鱼骨",
        "shed": "换羽期颜色会变暗",
        "tip": "颜色是鸟里最艳的，体质也是最娇的。低于 15℃ 就容易炸毛，换羽期断活食会卡羽、颜色发灰。",
        "ill": ["炸毛拒食", "卡羽", "球虫"],
        "no": "不要低于 15℃ 饲养，不要断活食",
        "legal": "free"
    },
    {
        "k": "degus", "name": "八齿鼠", "group": "小哺乳",
        "latin": "Octodon degus", "en": "Degu",
        "alias": ["德古鼠", "八齿鼠"], "size": "成体 25–30 cm（含尾）", "life": "6–8 年",
        "level": 3, "temper": "极活跃、好奇、需要同伴", "temp": [18, 24], "hum": [40, 60],
        "feed": "专用鼠粮 + 提摩西草 + 少量蔬菜；严禁糖和水果",
        "shed": "少量持续掉毛",
        "tip": "它是糖尿病患者——不能吃任何含糖食物，包括水果和蜂蜜零食。尾巴会“脱套”自割，抓尾巴等于让它断尾。",
        "ill": ["糖尿病", "白内障", "牙齿过长"],
        "no": "不要喂水果和甜食，不要抓尾巴，不要单养",
        "legal": "free"
    },
    {
        "k": "spiny-mouse", "name": "非洲刺毛鼠", "group": "小哺乳",
        "latin": "Acomys cahirinus", "en": "Spiny Mouse",
        "alias": ["刺鼠", "埃及刺鼠"], "size": "成体 10–12 cm", "life": "4–6 年",
        "level": 2, "temper": "群居、温和、动作快", "temp": [22, 28], "hum": [30, 50],
        "feed": "鼠粮 + 少量昆虫 + 种子，每周 2 次活食",
        "shed": "少量",
        "tip": "背上有一层硬毛，手感像刷子。它来自半干旱地区，怕潮不怕干，垫材长期潮湿会烂皮。",
        "ill": ["皮肤真菌", "脱毛", "牙齿过长"],
        "no": "不要用潮湿垫材，不要单只饲养",
        "legal": "free"
    },

    # ---------- 小哺乳（补充） ----------
    {
        "k": "capybara", "name": "水豚", "group": "小哺乳",
        "latin": "Hydrochoerus hydrochaeris", "en": "Capybara",
        "alias": ["水猪", "卡皮巴拉"], "size": "成体 100–130 cm，35–60 kg", "life": "8–12 年",
        "level": 3, "temper": "温和、群居、行动慢", "temp": [18, 28], "hum": [50, 80],
        "feed": "以禾本科草为主，配少量水豚颗粒；每天都要有草",
        "shed": "换毛不明显",
        "tip": "它不是「大号豚鼠」：必须有水池、围栏和足够草地，单只养会应激。购买前先确认当地对饲养场地和来源的要求。",
        "ill": ["皮肤干裂", "蹄部感染", "寄生虫"],
        "no": "不要养在室内笼箱，不要单只饲养，不要喂高淀粉食物",
        "legal": "free"
    },
    {
        "k": "raccoon", "name": "浣熊", "group": "小哺乳",
        "latin": "Procyon lotor", "en": "Raccoon",
        "alias": ["貉"], "size": "成体 40–70 cm，4–9 kg", "life": "10–16 年",
        "level": 3, "temper": "好奇、手巧、会拆家", "temp": [15, 28], "hum": [40, 70],
        "feed": "杂食：犬粮/猫粮为主，配果蔬与少量肉",
        "shed": "季节性换毛",
        "tip": "前爪灵活到能开门开锁，笼舍必须上锁；发情期咬人很凶。国内个人饲养要先落实合法来源和检疫，很多城市按外来物种管理。",
        "ill": ["肥胖", "寄生虫", "牙齿问题"],
        "no": "不要散养，不要与猫狗混养，不要投喂人类零食",
        "legal": "free"
    },
    {
        "k": "meerkat", "name": "狐獴", "group": "小哺乳",
        "latin": "Suricata suricatta", "en": "Meerkat",
        "alias": ["猫鼬", "丁满"], "size": "成体 25–35 cm，0.7–1 kg", "life": "10–14 年",
        "level": 3, "temper": "群居、警觉、爱打洞", "temp": [20, 30], "hum": [30, 50],
        "feed": "昆虫为主，配专用颗粒与少量肉",
        "shed": "换毛不明显",
        "tip": "必须成群养，单只会抑郁；需要沙地打洞和晒背点。它对温度和光照要求高，冬天要补灯。",
        "ill": ["佝偻病", "应激性腹泻", "寄生虫"],
        "no": "不要单只养，不要用猫砂盆代替沙地",
        "legal": "free"
    },
    {
        "k": "alpaca", "name": "羊驼", "group": "小哺乳",
        "latin": "Vicugna pacos", "en": "Alpaca", "inat": "Lama pacos",
        "alias": ["驼羊"], "size": "肩高 90–100 cm，55–75 kg", "life": "15–20 年",
        "level": 3, "temper": "温和，但会吐口水", "temp": [-5, 28], "hum": [30, 60],
        "feed": "干草 + 专用颗粒，少量精料",
        "shed": "每年剪毛一次",
        "tip": "是农场动物不是室内宠物，需要草地、遮阳棚和同伴；蹄甲要定期修。城市小区基本不具备条件。",
        "ill": ["蹄病", "毛球/消化道阻塞", "寄生虫"],
        "no": "不要养在室内或阳台，不要单只饲养",
        "legal": "free"
    },
    {
        "k": "prairie-dog", "name": "草原犬鼠", "group": "小哺乳",
        "latin": "Cynomys ludovicianus", "en": "Black-tailed Prairie Dog",
        "alias": ["土拨鼠"], "size": "成体 30–40 cm，0.7–1.4 kg", "life": "8–10 年",
        "level": 3, "temper": "群居、爱叫、会打洞", "temp": [18, 26], "hum": [30, 50],
        "feed": "提摩西草 + 专用颗粒，少量蔬菜",
        "shed": "季节性换毛",
        "tip": "必须群养并给足垫材打洞；它是草原动物，笼养容易肥胖和牙病。来源与检疫要先问清楚。",
        "ill": ["牙齿过长", "肥胖", "呼吸道感染"],
        "no": "不要单只饲养，不要喂高糖水果",
        "legal": "free"
    },
    {
        "k": "ferret", "name": "雪貂", "group": "小哺乳",
        "latin": "Mustela putorius furo", "en": "Ferret", "inat": "Mustela furo",
        "alias": ["貂"], "size": "成体 40–50 cm，0.7–1.5 kg", "life": "6–10 年",
        "level": 2, "temper": "活泼、好奇、爱钻洞", "temp": [18, 24], "hum": [40, 60],
        "feed": "专用貂粮或生骨肉，高蛋白高脂肪",
        "shed": "春秋换毛，掉毛量大",
        "tip": "怕热，超过 26℃ 容易中暑；需要每天出笼活动 2 小时以上。部分城市对饲养有额外规定，入手前先确认。",
        "ill": ["肾上腺疾病", "胰岛素瘤", "中暑"],
        "no": "不要喂猫粮狗粮长期代替，不要关在小笼子里",
        "legal": "free"
    },

    # ---------- 节肢（补充） ----------
    {
        "k": "hermit-crab", "name": "寄居蟹", "group": "节肢",
        "latin": "Coenobita clypeatus", "en": "Caribbean Hermit Crab",
        "alias": ["陆寄居蟹"], "size": "壳径 3–8 cm", "life": "10–20 年",
        "level": 2, "temper": "群居、夜间活动", "temp": [24, 28], "hum": [70, 85],
        "feed": "水果、蔬菜、鱼干、钙质补充",
        "shed": "蜕壳在壳内完成",
        "tip": "需要「陆区 + 湿区」两种底材和多个空壳供换壳，湿度低于 60% 会闷死。不要单只养。",
        "ill": ["脱壳失败", "脱水", "壳螨"],
        "no": "不要用干沙全干养，不要强行把蟹从壳里拽出来",
        "legal": "free"
    },
    {
        "k": "chinese-centipede", "name": "少棘蜈蚣", "group": "节肢",
        "latin": "Scolopendra subspinipes mutilans", "en": "Chinese Red-headed Centipede", "inat": "Scolopendra mutilans",
        "alias": ["红头蜈蚣", "药用蜈蚣"], "size": "成体 10–20 cm", "life": "5–8 年",
        "level": 3, "temper": "凶猛、速度快、有毒", "temp": [24, 28], "hum": [70, 85],
        "feed": "每周 1 次昆虫或小蟋蟀",
        "shed": "2–4 个月一次",
        "tip": "咬人很痛，红肿可持续数天；开盒必须用长镊子，绝不能上手。逃跑能力强，盒盖要压重物。",
        "ill": ["蜕皮失败", "脱水", "真菌感染"],
        "no": "不要徒手接触，不要与其它动物混养",
        "legal": "free"
    },
    {
        "k": "jumping-spider", "name": "跳蛛", "group": "节肢",
        "latin": "Phidippus regius", "en": "Regal Jumping Spider",
        "alias": ["佛罗里达跳蛛", "蝇虎"], "size": "成体 1.5–2 cm", "life": "1–2 年",
        "level": 1, "temper": "温和、好奇、会盯着人看", "temp": [24, 28], "hum": [50, 70],
        "feed": "每 2–3 天一只果蝇或小蟋蟀",
        "shed": "1–2 个月一次，会结薄网",
        "tip": "视力极好，会主动捕猎；小方盒 + 一点攀爬枝条就够。寿命短，公蛛交配后很快衰老。",
        "ill": ["蜕皮失败", "脱水", "拒食"],
        "no": "不要用大号饲养箱（找不到猎物），不要喷水过多",
        "legal": "free"
    },
    {
        "k": "metallic-tarantula", "name": "金属蓝捕鸟蛛", "group": "节肢",
        "latin": "Poecilotheria metallica", "en": "Gooty Sapphire Ornamental",
        "alias": ["蓝宝石捕鸟蛛", "金属蓝"], "size": "足展 15–18 cm", "life": "10–15 年（母）",
        "level": 3, "temper": "速度快、毒性较强、会瞬移", "temp": [24, 28], "hum": [75, 85],
        "feed": "每周 1–2 只蟋蟀或杜比亚",
        "shed": "2–4 个月一次",
        "tip": "Poecilotheria 属全部列入 CITES 附录 II，买卖需要合法来源与许可文件；它的毒液对人反应明显，不建议新手碰。",
        "ill": ["蜕皮失败", "脱水", "真菌感染"],
        "no": "不要上手，不要开盖不设防，不要无证买卖",
        "legal": "doc"
    },
    {
        "k": "black-thick-tail", "name": "黑粗尾蝎", "group": "节肢",
        "latin": "Androctonus bicolor", "en": "Black Thick-tailed Scorpion",
        "alias": ["黑粗尾"], "size": "成体 7–10 cm", "life": "5–8 年",
        "level": 3, "temper": "凶猛、毒性强", "temp": [26, 32], "hum": [30, 50],
        "feed": "每周 1 只蟋蟀或杜比亚",
        "shed": "3–6 个月一次",
        "tip": "属高危蝎，毒液可致剧痛、呕吐，儿童和过敏体质尤其危险。只适合有经验者，且必须双人操作、备好急救电话。",
        "ill": ["蜕皮失败", "脱水", "霉菌"],
        "no": "不要徒手抓，不要在儿童可触及处饲养",
        "legal": "free"
    },

    # ---------- 水生（观赏鱼虾） ----------
    {
        "k": "discus", "name": "七彩神仙", "group": "水生",
        "latin": "Symphysodon aequifasciatus", "en": "Discus",
        "alias": ["七彩", "神仙七彩"], "size": "成体 12–15 cm", "life": "8–12 年",
        "level": 3, "temper": "温和、群居、敏感", "temp": [28, 31], "hum": [0, 0],
        "feed": "专用汉堡/颗粒，少量多餐",
        "shed": "不蜕皮，靠换水维持水质",
        "tip": "水温要稳定在 28–30℃，pH 偏酸软水；它对水质波动极敏感，换水必须少量多次。新手最容易死在「水看着很清」上。",
        "ill": ["白点病", "肠炎", "鳃病"],
        "no": "不要与大鱼混养，不要一次大量换水",
        "legal": "free"
    },
    {
        "k": "guppy", "name": "孔雀鱼", "group": "水生",
        "latin": "Poecilia reticulata", "en": "Guppy",
        "alias": ["凤尾鱼"], "size": "成体 3–5 cm", "life": "1–2 年",
        "level": 1, "temper": "温和、活泼、繁殖快", "temp": [22, 28], "hum": [0, 0],
        "feed": "小型鱼颗粒，每天 1–2 次少量",
        "shed": "不蜕皮",
        "tip": "最容易上手的观赏鱼之一，但繁殖极快，几个月就能爆缸；公母比例建议 1:2。",
        "ill": ["白点病", "烂尾", "水霉"],
        "no": "不要与爱咬鳍的鱼混养，不要喂过量",
        "legal": "free"
    },
    {
        "k": "betta", "name": "斗鱼", "group": "水生",
        "latin": "Betta splendens", "en": "Siamese Fighting Fish",
        "alias": ["泰国斗鱼", "马尾斗鱼"], "size": "成体 5–7 cm", "life": "2–4 年",
        "level": 1, "temper": "好斗，只能单养", "temp": [24, 28], "hum": [0, 0],
        "feed": "斗鱼专用颗粒，每天 2–3 粒",
        "shed": "不蜕皮",
        "tip": "两条公鱼放一起会打到死；它需要 24℃ 以上的水和安静水面。小圆缸养不活，至少 10 升带过滤。",
        "ill": ["烂鳍", "白点病", "腹胀"],
        "no": "不要公鱼混养，不要用无加热的小圆缸",
        "legal": "free"
    },
    {
        "k": "neon-tetra", "name": "红绿灯鱼", "group": "水生",
        "latin": "Paracheirodon innesi", "en": "Neon Tetra",
        "alias": ["灯科鱼", "霓虹灯鱼"], "size": "成体 3–4 cm", "life": "3–5 年",
        "level": 2, "temper": "温和、群游", "temp": [22, 26], "hum": [0, 0],
        "feed": "小型颗粒或薄片，每天少量",
        "shed": "不蜕皮",
        "tip": "必须成群（10 条以上）才稳定，单养会躲角落；新缸要养水 2 周以上再下鱼。",
        "ill": ["白点病", "霓虹灯病", "水霉"],
        "no": "不要放进未养水的新缸，不要与大型鱼混养",
        "legal": "free"
    },
    {
        "k": "white-cloud-minnow", "name": "白云金丝", "group": "水生",
        "latin": "Tanichthys albonubes", "en": "White Cloud Mountain Minnow",
        "alias": ["唐鱼", "白云山鱼"], "size": "成体 3–4 cm", "life": "3–5 年",
        "level": 1, "temper": "温和、耐低温、群游", "temp": [16, 24], "hum": [0, 0],
        "feed": "小型颗粒或薄片，每天少量",
        "shed": "不蜕皮",
        "tip": "我国特有鱼，野外种群是国家二级保护动物，只能养人工繁育个体；它耐低温，不用加热棒也能过冬。",
        "ill": ["白点病", "水霉"],
        "no": "不要购买来路不明的野生个体，不要放生",
        "legal": "doc"
    },
    {
        "k": "angelfish", "name": "神仙鱼", "group": "水生",
        "latin": "Pterophyllum scalare", "en": "Angelfish",
        "alias": ["燕鱼"], "size": "成体 12–15 cm（含鳍）", "life": "5–10 年",
        "level": 2, "temper": "温和但会吃小鱼", "temp": [24, 28], "hum": [0, 0],
        "feed": "颗粒 + 少量丰年虾",
        "shed": "不蜕皮",
        "tip": "需要高缸（至少 45 cm 水深）；配对后会护卵、驱赶其它鱼。幼鱼期水质不稳容易融鳍。",
        "ill": ["白点病", "融鳍", "肠炎"],
        "no": "不要与灯科小鱼混养，不要养在矮缸",
        "legal": "free"
    },
    {
        "k": "flowerhorn", "name": "罗汉鱼", "group": "水生",
        "latin": "Amphilophus citrinellus × 杂交", "en": "Flowerhorn", "inat": "Amphilophus labiatus × trimaculatus",
        "alias": ["花罗汉"], "size": "成体 25–30 cm", "life": "8–12 年",
        "level": 2, "temper": "凶猛、认人、会咬手", "temp": [26, 30], "hum": [0, 0],
        "feed": "罗汉专用颗粒，少量多次",
        "shed": "不蜕皮",
        "tip": "是人工杂交鱼，不能放生；单养、大缸、强过滤。起头大小和基因、水质、喂食都有关，别信「药水催头」。",
        "ill": ["肠炎", "头洞病", "白点病"],
        "no": "不要混养，不要用药物催头，不要放生",
        "legal": "free"
    },
    {
        "k": "blood-parrot", "name": "血鹦鹉", "group": "水生",
        "latin": "Amphilophus 杂交", "en": "Blood Parrot Cichlid", "inat": "Amphilophus citrinellus × Vieja melanurus",
        "alias": ["鹦鹉鱼"], "size": "成体 15–20 cm", "life": "8–12 年",
        "level": 2, "temper": "温和、嘴合不拢", "temp": [25, 28], "hum": [0, 0],
        "feed": "专用增色颗粒，少量多次",
        "shed": "不蜕皮",
        "tip": "人工杂交鱼，嘴畸形咬不碎食物，颗粒要小；水质差会褪色发白。不能放生。",
        "ill": ["褪色", "肠炎", "白点病"],
        "no": "不要喂大颗粒，不要放生",
        "legal": "free"
    },
    {
        "k": "cherry-shrimp", "name": "樱花虾", "group": "水生",
        "latin": "Neocaridina davidi", "en": "Cherry Shrimp",
        "alias": ["观赏虾", "黑壳虾"], "size": "成体 2–3 cm", "life": "1–2 年",
        "level": 1, "temper": "温和、群居、吃藻", "temp": [20, 26], "hum": [0, 0],
        "feed": "藻类 + 虾粮，每周 2–3 次",
        "shed": "2–4 周蜕壳一次",
        "tip": "对铜离子和杀虫剂极敏感，缸里不能用含铜药；蜕壳期要有躲避物，否则会被同类吃掉。",
        "ill": ["蜕壳失败", "白肉病", "被鱼捕食"],
        "no": "不要与大型鱼混养，不要用含铜药物",
        "legal": "free"
    },
    {
        "k": "algae-eater", "name": "金苔鼠", "group": "水生",
        "latin": "Gyrinocheilus aymonieri", "en": "Siamese Algae Eater",
        "alias": ["青苔鼠", "食藻鳅"], "size": "成体 15–25 cm", "life": "8–10 年",
        "level": 2, "temper": "幼体温和，成体会吸鱼", "temp": [24, 28], "hum": [0, 0],
        "feed": "藻类 + 沉底饲料",
        "shed": "不蜕皮",
        "tip": "小时候吃藻，长大后常去吸病鱼体表，反而加重病情；大缸单养更稳。",
        "ill": ["白点病", "消瘦", "吸盘损伤"],
        "no": "不要与行动缓慢的鱼混养，不要指望它替代过滤",
        "legal": "free"
    },
    {
        "k": "goldfish", "name": "金鱼", "group": "水生",
        "latin": "Carassius auratus", "en": "Goldfish",
        "alias": ["鲫鱼系观赏鱼", "草金"], "size": "成体 10–25 cm", "life": "10–20 年",
        "level": 1, "temper": "温和、能吃能拉", "temp": [10, 26], "hum": [0, 0],
        "feed": "金鱼颗粒，每天 1–2 次少量",
        "shed": "不蜕皮",
        "tip": "冷水鱼，不需要加热棒；但它排泄量大，缸要够大、过滤要强。小圆缸养金鱼等于慢性缺氧。",
        "ill": ["白点病", "烂尾", "鱼鳔失调"],
        "no": "不要用无过滤的小圆缸，不要喂过量",
        "legal": "free"
    },
    {
        "k": "koi", "name": "锦鲤", "group": "水生",
        "latin": "Cyprinus rubrofuscus", "en": "Koi",
        "alias": ["鲤鱼", "日本锦鲤"], "size": "成体 40–80 cm", "life": "20–35 年",
        "level": 3, "temper": "温和、认食", "temp": [8, 26], "hum": [0, 0],
        "feed": "锦鲤专用饲料，随水温调整投喂量",
        "shed": "不蜕皮",
        "tip": "是池塘鱼，不是鱼缸鱼；一条成体需要至少 1 吨水。水温低于 10℃ 要停食，喂了会积食。",
        "ill": ["锦鲤疱疹病毒", "烂鳃", "寄生虫"],
        "no": "不要养在小缸，不要低温继续喂食，不要放生",
        "legal": "free"
    },
    {
        "k": "redclaw-crayfish", "name": "澳洲淡水龙虾", "group": "水生",
        "latin": "Cherax quadricarinatus", "en": "Redclaw Crayfish",
        "alias": ["鳌虾", "蓝魔虾"], "size": "成体 15–25 cm", "life": "3–5 年",
        "level": 2, "temper": "好斗、会夹人", "temp": [24, 28], "hum": [0, 0],
        "feed": "虾粮 + 蔬菜 + 少量鱼肉",
        "shed": "1–2 个月蜕壳一次",
        "tip": "蜕壳期最脆弱，要有躲避罐；它是外来种，绝对不能放生到自然水域。",
        "ill": ["蜕壳失败", "水霉", "互相残杀"],
        "no": "不要放生，不要高密度混养",
        "legal": "free"
    },
]
# ---------------------------------------------------------------------------
# 不能养的：个人无证持有即违法，或根本无法提供合法饲养条件。
# 这里只做「识别 + 劝退」，不是饲养指南，所以不给饲养参数。
# law  法规依据（简写）
# why  为什么个人养不了
# risk 硬来的后果
# instead 想养类似的，可以改养谁
# ---------------------------------------------------------------------------
FORBIDDEN = [
    {
        "k": "green-iguana", "name": "绿鬣蜥", "group": "蜥蜴",
        "latin": "Iguana iguana", "en": "Green Iguana", "alias": ["绿鬣"],
        "law": "CITES 附录 II，在我国按国家二级重点保护野生动物管理",
        "short": "按国家二级管理",
        "why": "野外种群受国际贸易管制，个人饲养必须取得人工繁育许可并有种源证明。"
               "加上它能长到 1.8 米，成年后需要整面墙的箱体，绝大多数家庭给不了。",
        "risk": "无证饲养可被没收、罚款；非法收购、出售还可能追究刑责。",
        "instead": "bearded-dragon"
    },
    {
        "k": "veiled-chameleon", "name": "高冠变色龙", "group": "蜥蜴",
        "latin": "Chamaeleo calyptratus", "en": "Veiled Chameleon", "alias": ["变色龙"],
        "law": "CITES 附录 II，在我国按国家二级重点保护野生动物管理（变色龙科全部列入）",
        "short": "按国家二级管理",
        "why": "整个避役科都在附录 II 内，国内没有面向个人的合法购买渠道；"
               "而且它对通风、UVB、饮水要求极高，是公认的高死亡率物种。",
        "risk": "买卖双方都可能被追责，快递活体还涉及运输违规。",
        "instead": "madagascar-day-gecko"
    },
    {
        "k": "sulcata", "name": "苏卡达陆龟", "group": "龟",
        "latin": "Centrochelys sulcata", "en": "African Spurred Tortoise", "alias": ["苏卡达", "苏"],
        "law": "CITES 附录 II，在我国按国家二级重点保护野生动物管理（陆龟科全部列入）",
        "short": "按国家二级管理",
        "why": "所有陆龟科物种都受保护，个人无证饲养一律违法。它还能长到七八十厘米、"
               "活过五十年，需要户外场地和日照。",
        "risk": "这是近年来查处最多的异宠案件类型之一，买卖、运输、寄养都可能被认定违法。",
        "instead": "razorback-musk"
    },
    {
        "k": "hermanns-tortoise", "name": "赫曼陆龟", "group": "龟",
        "latin": "Testudo hermanni", "en": "Hermann's Tortoise", "alias": ["赫曼"],
        "law": "CITES 附录 II，在我国按国家二级重点保护野生动物管理",
        "short": "按国家二级管理",
        "why": "体型小、看着很适合家养，恰恰是最容易被误买的陆龟；"
               "但它在国内同样属于保护物种，个人不能无证持有。",
        "risk": "同样是高查处率的物种，网络上「包邮包活」的卖家基本都无证。",
        "instead": "musk-turtle"
    },
    {
        "k": "burmese-python", "name": "缅甸蟒", "group": "蛇",
        "latin": "Python bivittatus", "en": "Burmese Python", "alias": ["缅甸蟒"],
        "law": "《国家重点保护野生动物名录》国家一级",
        "short": "国家一级",
        "why": "国家一级保护动物，任何个人饲养都必须有严格的审批，宠物用途基本不可能获批；"
               "成年体长可达四米以上，本身也有安全风险。",
        "risk": "非法猎捕、收购、运输、出售国家一级保护动物，可处五年以上有期徒刑。",
        "instead": "ball-python"
    },
    {
        "k": "reticulated-python", "name": "网纹蟒", "group": "蛇",
        "latin": "Malayopython reticulatus", "en": "Reticulated Python", "alias": ["网纹蟒"],
        "law": "《国家重点保护野生动物名录》国家一级；CITES 附录 II",
        "short": "国家一级",
        "why": "世界最长的蛇，能超过六米。国内属国家一级保护，个人不可能合法持有。",
        "risk": "同属一级保护动物，刑事风险极高；且大型蟒蛇对饲养者本人有致命风险。",
        "instead": "corn-snake"
    },
    {
        "k": "green-tree-python", "name": "绿树蟒", "group": "蛇",
        "latin": "Morelia viridis", "en": "Green Tree Python", "alias": ["绿树蟒"],
        "law": "CITES 附录 II，在我国按国家二级重点保护野生动物管理",
        "short": "按国家二级管理",
        "why": "虽然国外人工繁育成熟，但国内没有对个人的合法流通渠道；"
               "它对温湿度容错极低，是新手最容易养死的蛇之一。",
        "risk": "无证买卖同属违法，来源无法证明时一律按非法收购处理。",
        "instead": "milk-snake"
    },
    {
        "k": "boa-constrictor", "name": "红尾蚺", "group": "蛇",
        "latin": "Boa constrictor", "en": "Red-tailed Boa", "alias": ["红尾蚺", "BCC"],
        "law": "CITES 附录 II，在我国按国家二级重点保护野生动物管理",
        "short": "按国家二级管理",
        "why": "所有蚺科（Boidae）都列入附录 II；成体两米以上，需要大型饲养箱和长期温控。",
        "risk": "无证持有被查即没收，情节严重的按危害珍贵、濒危野生动物罪处理。",
        "instead": "florida-kingsnake"
    },
    {
        "k": "water-monitor", "name": "泽巨蜥", "group": "蜥蜴",
        "latin": "Varanus salvator", "en": "Water Monitor", "alias": ["巨蜥", "五爪金龙"],
        "law": "《国家重点保护野生动物名录》国家一级（我国所有巨蜥属物种均为一级）",
        "short": "国家一级",
        "why": "国内所有巨蜥都是国家一级保护动物。它能长到两米，需要近乎动物园级别的场地。",
        "risk": "一级保护动物，非法交易可判五年以上；被咬伤、尾击致伤的案例也不少。",
        "instead": "australian-water-dragon"
    },
    {
        "k": "macaque", "name": "猕猴", "group": "灵长",
        "latin": "Macaca mulatta", "en": "Rhesus Macaque", "alias": ["猴子"],
        "law": "《国家重点保护野生动物名录》国家二级",
        "short": "国家二级",
        "why": "所有我国原产灵长类都是保护动物，个人不能作为宠物饲养；"
               "灵长类还有传播人兽共患病的风险，且社会性需求无法在家庭满足。",
        "risk": "无证饲养违法，且多地明令禁止；弃养后无法回归野外。",
        "instead": "fancy-rat"
    },
    {
        "k": "slow-loris", "name": "蜂猴", "group": "灵长",
        "latin": "Nycticebus coucang", "en": "Slow Loris", "alias": ["懒猴"],
        "law": "《国家重点保护野生动物名录》国家一级；CITES 附录 I",
        "short": "国家一级",
        "why": "国家一级保护，且是全球受威胁最严重的灵长类之一。"
               "网上流传的「可爱视频」背后基本是盗猎—拔牙—非法交易链条。",
        "risk": "买卖均构成犯罪；被拔牙的个体几乎无法存活。",
        "instead": "sugar-glider"
    },
    {
        "k": "eagle-owl", "name": "雕鸮", "group": "鸟",
        "latin": "Bubo bubo", "en": "Eurasian Eagle-Owl", "alias": ["猫头鹰"],
        "law": "《国家重点保护野生动物名录》国家二级（我国所有鸮形目均为二级以上）",
        "short": "国家二级",
        "why": "所有猫头鹰都是保护动物，且全部为 CITES 附录 II。"
               "它们是纯肉食猛禽，需要整只鼠类，家庭饲养无法满足营养与空间需求。",
        "risk": "买卖、捡拾幼鸟饲养都可能违法；私自「救助」后不放归也会被追责。",
        "instead": "cockatiel"
    },
    {
        "k": "giant-salamander", "name": "大鲵", "group": "两栖",
        "latin": "Andrias davidianus", "en": "Chinese Giant Salamander", "alias": ["娃娃鱼"],
        "law": "《国家重点保护野生动物名录》国家二级；CITES 附录 I",
        "short": "国家二级",
        "why": "国家二级保护，野生个体极度濒危。虽然有人工养殖产业，但那是持证养殖场，"
               "个人买来当宠物仍属违法。",
        "risk": "餐馆与网络销售的「娃娃鱼」多为违规流通，购买同样要担责。",
        "instead": "axolotl"
    },
    {
        "k": "pangolin", "name": "穿山甲", "group": "其他",
        "latin": "Manis pentadactyla", "en": "Chinese Pangolin", "alias": ["鲮鲤"],
        "law": "《国家重点保护野生动物名录》国家一级；CITES 附录 I",
        "short": "国家一级",
        "why": "国家一级保护，且已从药典移除。它只吃特定蚂蚁和白蚁，人工环境几乎无法养活。",
        "risk": "任何买卖、持有、食用行为都构成犯罪，是重点打击对象。",
        "instead": "giant-millipede"
    },
    {
        "k": "siamese-crocodile", "name": "暹罗鳄", "group": "其他",
        "latin": "Crocodylus siamensis", "en": "Siamese Crocodile", "alias": ["鳄鱼"],
        "law": "CITES 附录 I；《国家重点保护野生动物名录》对应物种按一级管理",
        "short": "附录 I / 一级管理",
        "why": "鳄类全部受严格管制，个人饲养需要野生动物人工繁育许可证、场地审核与安全评估，"
               "普通住宅不可能通过。",
        "risk": "无证饲养属违法；一旦逃逸伤人是重大公共安全事件。",
        "instead": "razorback-musk"
    },
    {
        "k": "red-eared-slider", "name": "巴西龟", "group": "龟",
        "latin": "Trachemys scripta elegans", "en": "Red-eared Slider", "alias": ["红耳龟", "巴西"],
        "law": "列入《重点管理外来入侵物种名录》，禁止放生或遗弃；多地另有禁售、禁养规定",
        "short": "外来入侵物种",
        "why": "它是最典型的外来入侵龟：适应力强、繁殖快，放生一条河就能挤掉本地龟。"
               "虽然市场上仍有人卖，但正规渠道已收紧，很多地方明令禁止销售与放生。",
        "risk": "放生属违法行为，可被处罚；弃养后它极难再被回收，等于把问题丢给野外。",
        "instead": "razorback-musk"
    },
    {
        "k": "snapping-turtle", "name": "小鳄龟", "group": "龟",
        "latin": "Chelydra serpentina", "en": "Common Snapping Turtle", "alias": ["鳄龟"],
        "law": "列入《重点管理外来入侵物种名录》，禁止放生或遗弃；养殖需备案",
        "short": "外来入侵物种",
        "why": "咬合力极大、成年后体型惊人，弃养率极高；一旦进入自然水域会大量捕食本地鱼虾和幼龟。",
        "risk": "放生、随意弃养违法；咬伤事件每年都有，家庭饲养安全风险高。",
        "instead": "razorback-musk"
    },
]

GROUPS = ["全部", "守宫", "蜥蜴", "蛇", "龟", "两栖", "水生", "节肢", "昆虫", "鸟", "小哺乳"]
FORBIDDEN_GROUPS = ["全部", "蜥蜴", "蛇", "龟", "两栖", "鸟", "灵长", "其他"]


def all_species():
    return SPECIES


def all_forbidden():
    return FORBIDDEN


def by_key(k: str):
    for s in SPECIES:
        if s["k"] == k:
            return s
    return None


def forbidden_by_key(k: str):
    for s in FORBIDDEN:
        if s["k"] == k:
            return s
    return None


def search(q: str = "", group: str = ""):
    q = (q or "").strip().lower()
    out = []
    for s in SPECIES:
        if group and group != "全部" and s["group"] != group:
            continue
        if q:
            hay = " ".join([s["name"], s["latin"].lower(), s["en"].lower(),
                            s["group"]] + [a.lower() for a in s.get("alias", [])])
            if q not in hay:
                continue
        out.append(s)
    return out


def search_forbidden(q: str = "", group: str = ""):
    q = (q or "").strip().lower()
    out = []
    for s in FORBIDDEN:
        if group and group != "全部" and s["group"] != group:
            continue
        if q:
            hay = " ".join([s["name"], s["latin"].lower(), s["en"].lower(),
                            s["group"], s.get("law", "")] + [a.lower() for a in s.get("alias", [])])
            if q not in hay:
                continue
        out.append(s)
    return out
