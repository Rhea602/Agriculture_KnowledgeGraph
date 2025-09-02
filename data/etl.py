import pandas as pd
from py2neo import Graph,Node,Relationship

graph = Graph("bolt://localhost:7687", user='neo4j', password='Rhea@123') 

# 转换成csv文件
df=pd.read_excel("小麦.xlsx")
df.to_csv("wheat.csv",index=False,encoding='utf-8')

# 去重
df=df.drop_duplicates(subset="库编号",keep="last")

# 提取地区信息
columns_region=['原产地','省','东经','北纬','种类']
df_region=df[columns_region].copy()

# 提取作物信息
columns_wheat=['库编号','统一编号','保存单位','品种名称','译名','科名','属名','学名','系谱','育成年限','芒','壳色','粒色','冬春性','成熟期','穗粒数','穗长','株高','千粒重','粗蛋白','赖氨酸','沉淀值','硬度','容重','抗旱性','耐涝性','芽期耐盐','苗期耐盐','田间抗寒性','人工抗寒性','其它']
df_wheat=df[columns_wheat].copy()

# 提取病害信息
columns_disease=['条锈严重度','条锈反应型','条锈普遍率','叶锈严重度','叶锈反应型','叶锈普遍率','秆锈严重度','秆锈反应型','秆锈普遍率','白粉严重度','白粉反应型','黄矮病','赤霉病病穗','赤霉病病指','赤霉病指数','赤霉病抗性','根腐叶病级','根腐穗病级']
df_disease=df[columns_disease].copy()

# 创建小麦节点
def create_wheat_nodes(df_wheat,key_col):
    for _,row in df_wheat.iterrows():
        properties={k:v for k,v in row.items() if pd.notna(v)}
        node=Node("Wheat", **properties)
        graph.merge(node,"Wheat",key_col)

# 创建地区节点
def create_region_nodes(df_region,key_col):
     # key_col不能存在空值，过滤掉原产地为空的行
    df_filtered = df_region.dropna(subset=[key_col])
    for _,row in df_filtered.iterrows():
        properties={k:v for k,v in row.items() if pd.notna(v)}
        node=Node("Region", **properties)
        graph.merge(node,"Region",key_col)

# 创建病害节点
def create_disease_nodes(df_disease, key_col="病害名称"):
    # 具体作物对应的病害情况保存在关系中，节点只保留基本信息
    # 定义所有病害名称列表
    disease_names = [
        "条锈病", "叶锈病", "秆锈病",
        "白粉病", "黄矮病", "赤霉病", "根腐病"
    ]
    
    for name in disease_names:
        disease_node = Node("Disease", 病害名称=name)
        graph.merge(disease_node, "Disease", key_col)

# 构建作物与种植地的关系
def create_plant_relations(df):
    for _,row in df.iterrows():
        node_wheat=graph.nodes.match("Wheat",库编号=row["库编号"]).first()
        node_region=graph.nodes.match("Region",原产地=row["原产地"]).first()
        if node_wheat and node_region:
            rel=Relationship(node_wheat,"GROWS_IN",node_region)
            graph.merge(rel)

# 构建作物与病害的关系
def create_disease_relations(df):
    disease_columns = [
        "条锈严重度", "条锈反应型", "条锈普遍率",
        "叶锈严重度", "叶锈反应型", "叶锈普遍率",
        "秆锈严重度", "秆锈反应型", "秆锈普遍率",
        "白粉严重度", "白粉反应型",
        "黄矮病",
        "赤霉病病穗", "赤霉病病指", "赤霉病指数", "赤霉病抗性",
        "根腐叶病级", "根腐穗病级"
    ]
    disease_info = {}
    for index,row in df.iterrows():
        node_wheat=graph.nodes.match("Wheat",库编号=row["库编号"]).first()
        # 对病害数据进行分类，通过前缀匹配
        for col in disease_columns:
            prefix=col[:2]
            if prefix not in disease_info:
                disease_info[prefix] = {}
            disease_info[prefix][col] = row[col]

        # 匹配Disease节点，创建关系
        for prefix,attrs in disease_info.items():
            disease_name=prefix+"病"
            node_disease=graph.nodes.match("Disease",病害名称=disease_name).first()

            relation_props = {k: v for k, v in attrs.items() if pd.notna(v)}
            # 创建关系 (Wheat)-[AFFECTED_BY]->(Disease)，并设置关系属性
            rel = Relationship(node_wheat, "AFFECTED_BY", node_disease, **relation_props)
            graph.merge(rel)

def main():
    # 创建节点
    create_wheat_nodes(df_wheat,"库编号")
    create_region_nodes(df_region,"原产地")
    create_disease_nodes(df_disease,"病害名称")

    # 关联关系
    create_plant_relations(df)
    create_disease_relations(df)

if __name__=="__main__":
    main()