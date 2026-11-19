import hashlib,re,unicodedata
import numpy as np
from sklearn.pipeline import make_pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.model_selection import train_test_split
from sklearn.metrics import f1_score,confusion_matrix
LABELS=['labor','housing','consumer']
def split_statements(facts):
    # 同一卷宗可能既问欠薪又问退租：按句读拆分来访原话，每段视为一桩独立事项
    return [p.strip() for p in re.split(r'[。！？；;\r\n]+',facts) if p.strip()]
def statement_digest(text):
    # 归一化原话摘要：仅忽略空白与全半角差异，字面有改动即视为事项变更
    return hashlib.sha256(''.join(unicodedata.normalize('NFKC',text).casefold().split()).encode()).hexdigest()
def _corpus():
    bases={'labor':['工资拖欠 工时 劳动 合同 加班 报酬 单位 用工','公司没有发工资 劳动报酬 加班工时 拖欠薪水','用工单位 劳动合同 薪资 考勤 解除工作'], 'housing':['租房 住房 房屋 租赁 押金 房东 退租 维修','租赁房屋到期 房东不退押金 租房维修','住房租约 退租 租金 房屋漏水 物业'], 'consumer':['购物 消费 商品 退款 质量 订单 商家 收据','商家出售商品损坏 消费退款 订单 收据','购买电器 商品质量 保修 消费者 退款']}
    texts=[];ys=[]
    for label,phrases in bases.items():
        for i in range(36):texts.append(phrases[i%len(phrases)]+f' 模拟行政来访编号{i} '+'请协助登记分流');ys.append(label)
    return texts,ys
def _train():
    texts,ys=_corpus()
    train,test=train_test_split(np.arange(len(texts)),test_size=.25,random_state=34,stratify=ys)
    model=make_pipeline(TfidfVectorizer(analyzer='char',ngram_range=(2,3)),MultinomialNB(alpha=.5)).fit([texts[i] for i in train],[ys[i] for i in train])
    predicted=model.predict([texts[i] for i in test])
    metrics={'macro_f1':float(f1_score([ys[i] for i in test],predicted,average='macro')),'confusion_matrix':confusion_matrix([ys[i] for i in test],predicted,labels=LABELS).tolist(),'labels':LABELS,'train_count':len(train),'test_count':len(test),'seed':34,'threshold':.68,'dataset_sha256':hashlib.sha256(chr(10).join(texts).encode()).hexdigest(),'source':'主题模板合成文本，仅验证内部行政分流；不是法律意见'}
    return model,metrics
def _predict(model,text):
    proba=model.predict_proba([text])[0];idx=int(np.argmax(proba))
    return str(model.classes_[idx]),float(proba[idx])
def classify(text):
    model,metrics=_train();label,confidence=_predict(model,text)
    return label,confidence,metrics
def classify_statements(facts):
    statements=split_statements(facts)
    if not statements:raise ValueError('未拆分出有效事项，请补充来访事实')
    model,metrics=_train()
    return [(s,*_predict(model,s)) for s in statements],metrics
