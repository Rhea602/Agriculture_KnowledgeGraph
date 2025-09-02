# -*- coding: utf-8 -*-

import os
import json
import types
from tencentcloud.common import credential
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.hunyuan.v20230901 import hunyuan_client, models

from py2neo import Graph, Node, Relationship
import pandas as pd

SECRET_ID="Your_Secret_ID"
SECRET_KEY="Your_Secret_Key"

PROMPT_TO_CYPHER = """
    任务：将用户问题转换为 Neo4j 的 Cypher 查询语句。
    
    知识图谱结构：
    - 实体类型：
      - Wheat（小麦）：属性有
          "品种名称"（该小麦的具体名称，一般提问中给出的中文名称均指该属性）、
          "库编号"（小麦在作物库中的编号，唯一）
          "统一编号"（小麦的统一编号，唯一）
          "保存单位"（小麦存储的单位）
          "译名"、"科名"、"属名"、"学名"
      - Region（地区）：属性有
          "原产地"（详细地理位置）、
          "省"（原产地所在省份，无“省”字，查询语句中要删去“省”）、
          "东经"（原产地对应东经值）、
          "北纬"（原产地对应北纬值）、
          "种类"（包括中国和国外，用以区分是我国品种还是引进品种）
      - Disease（病虫害）：属性有"病害名称"（病害的具体名称）
    - 关系类型：
      - GROWS_IN：Wheat -[:GROWS_IN]-> Region（作物种植于地区）
      - AFFECTED_BY：Crop -[:AFFECTED_BY]-> Disease（作物受病虫害影响）：
          条锈病关联的属性有："条锈严重度", "条锈反应型", "条锈普遍率"
          叶锈病关联的属性有："叶锈严重度", "叶锈反应型", "叶锈普遍率"
          秆锈病关联的属性有："秆锈严重度", "秆锈反应型", "秆锈普遍率"
          白粉病关联的属性有："白粉严重度", "白粉反应型"
          黄矮病关联的属性有："黄矮病"
          赤霉病关联的属性有："赤霉病病穗", "赤霉病病指", "赤霉病指数", "赤霉病抗性"
          根腐病关联的属性有："根腐叶病级", "根腐穗病级"
          （如果问题问的是某种作物对某种病害的程度、病害的属性，则查询的该作物与该病害的[AFFECTED_BY]关系的属性即可，注意不是病害节点的属性）
    
    用户问题：{question}
    请输出严格符合 Neo4j 语法的 Cypher 语句，无需额外解释，无需额外符号，纯文本形式。
    """

PROMPT_TO_NATURAL_LANGUAGE = """
    用户问题：{question}
    Neo4j 查询结果：{result}
    请将查询结果对应转换成自然语言，要求一一对应，不额外解释。若出现查询结果完全一样的情况，只需陈述其一即可。严格要求：对于名称等专业名词不允许进行修改，无需任何额外解释，不应出现“等”字样。
    如果查询结果为空，回复“抱歉，暂未查询到相关信息。”
    """

def natural_language_to_cypher(question):
    try:
        cred = credential.Credential(SECRET_ID, SECRET_KEY)
        client = hunyuan_client.HunyuanClient(cred, "")
    
        req = models.ChatCompletionsRequest()
        params = {
            "Model": "hunyuan-turbos-latest",
            "Messages": [
                {
                    "Role": "user",
                    "Content": PROMPT_TO_CYPHER.format(question=question)
                }
            ]
        }
        req.from_json_string(json.dumps(params))
    
        # 返回的resp是一个ChatCompletionsResponse的实例，与请求对象对应
        resp = client.ChatCompletions(req)
        return resp.Choices[0].Message.Content

    except TencentCloudSDKException as err:
        return f"API调用失败：{err}"
    
def query_neo4j(cypher):
    graph = Graph("bolt://localhost:7687", user='neo4j', password='Rhea@123')    
    result = graph.run(cypher).data()
    return result

def cypher_result_to_natural_language(result, question):
    try:
        cred = credential.Credential(SECRET_ID, SECRET_KEY)
        client = hunyuan_client.HunyuanClient(cred, "")
        req = models.ChatCompletionsRequest()
        params = {
                "Model": "hunyuan-turbos-latest",
                "Messages": [
                    {
                        "Role": "user",
                        "Content": PROMPT_TO_NATURAL_LANGUAGE.format(question=question, result=result)
                    }
                ]
            }
        req.from_json_string(json.dumps(params))
        resp = client.ChatCompletions(req)
        return resp.Choices[0].Message.Content

    except TencentCloudSDKException as err:
        return f"结果转换失败：{err}"
    
def main():
    while True:
        question=input("\n输入问题：")
        if question.lower()=='q':
            break
        #1.自然语言转cypher
        cypher=natural_language_to_cypher(question)
        print(f"生成的Cypher:{cypher}")
        
        #2.查询知识图谱
        result=query_neo4j(cypher)
        print(f"Neo4j查询结果：{result}")
        
        #3.结果转自然语言
        answer=cypher_result_to_natural_language(result,question)
        print(f"最终回答：{answer}")

if __name__=="__main__":
    main()