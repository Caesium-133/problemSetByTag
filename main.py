import streamlit as st
import pymysql
import pandas as pd
import numpy as np
from st_aggrid import AgGrid
import st_aggrid as sa

db = pymysql.connect(host="localhost", port=3306, user="root", password="123456", db="problem_set")
cursor = db.cursor()


def query(SQL):
    cursor.execute(SQL)
    return cursor.fetchall()


def getKey(d: dict, value):
    return list(d.keys())[list(d.values()).index(value)]


with st.sidebar:
    sub_sql = "SELECT sid,subjectName FROM subjects;"
    subs = query(sub_sql)
    if subs == ():
        st.info("还没添加学科呢")
        selectedSubjectId = 0
    else:
        subs = dict(subs)
        selectedSubject = st.selectbox("选择一个学科", [sub for sub in subs.values()])
        selectedSubjectId = getKey(subs, selectedSubject)
    subIn = st.text_input("添加学科")
    if st.button("确定"):
        try:
            if subIn!='':
                cursor.execute(f"insert into subjects(subjectName) values ('{subIn}')")
                db.commit()
                st.success("添加成功")
        except(Exception) as e:
            st.write(e)

if selectedSubjectId == 0:
    st.info("先去侧边栏添加一个学科吧")
else:
    whatToDo = st.selectbox("要做什么？", ["添加一道题", "来题", "管理"])

    if whatToDo == "添加一道题":
        book_sql = "SELECT bid,bookName FROM books;"
        books = query(book_sql)
        bookOK = 0
        if books == ():
            st.info("一本书都没有，先去管理tab添加一本吧")
        else:
            books = dict(books)
            selectedBook = st.selectbox("选择书", [book for book in books.values()])
            selectedBookId = getKey(books, selectedBook)
            bookOK = 1
        pageIn = st.text_input("输入页码")
        numIn = st.text_input("输入题号")
        contentIn = st.text_area("输入题目")
        remarkIn = st.text_area("输入评论")
        answerIn = st.text_area("输入答案")
        starIn = st.number_input("输入星级", value=0)
        tag_sql = f"select tid,tagName from tags where sid={selectedSubjectId};"
        tags = query(tag_sql)
        tagOK = 0
        if tags == ():
            st.info("一个tag都没有，快去管理tab添加")
        else:
            tags = dict(tags)
            selectedTags = st.multiselect("选择tag", [tag for tag in tags.values()])
            selectedTagIds = [getKey(tags, tag) for tag in selectedTags]
            tagOK = 1
        if st.button("确定"):
            if not (tagOK and bookOK):
                st.warning("还有东西没选呢吧，书或tag，添加了吗？学科选的对吗？")
            else:
                try:
                    getLastPid_sql = "select max(pid) from problems;"
                    lastPid = query(getLastPid_sql)[0][0]
                    addProb_sql = f"insert into problems (sid,bid,page,num,content,remark,answer,star) " \
                                  f"values ({selectedSubjectId},{selectedBookId},'{pageIn}','{numIn}','{contentIn}','{remarkIn}','{answerIn}',{int(starIn)});"
                    cursor.execute(addProb_sql)
                    for tagId in selectedTagIds:
                        addProbTag_sql = f"insert into prob_tag (pid,tid) values ({lastPid + 1},{tagId});"
                        cursor.execute(addProbTag_sql)
                    db.commit()
                    st.success("添加成功")
                except(Exception) as e:
                    db.rollback()
                    st.warning("没有添加成功")
                    st.write(e)

    if whatToDo == "来题":
        allColumns = ['pid', 'bookName', 'page', 'num', 'content', 'remark', 'answer', 'star']
        allProblems_sql = f"select pid,bookName,page,num,content,remark,answer,star from problems INNER JOIN books on problems.bid=books.bid where sid={selectedSubjectId};"
        allProblems = query(allProblems_sql)
        if allProblems == ():
            st.info("这个学科下还没添加题呢")
        else:
            allProblemsDF = pd.DataFrame(allProblems)
            allProblemsDF.columns = allColumns

            # 构建题目-tag表
            prob_tag_sql = f"select pid,tid from prob_tag;"
            prob_tag = query(prob_tag_sql)
            if prob_tag == ():
                st.info("最好先给题目加点tag，没有题目就先加题目")
            prob_tag = list(prob_tag)
            maxTagLen_sql = f"select max(cnt) from (select count(tid) cnt from prob_tag group by pid) a;".replace(
                '[', '').replace(']', '')
            maxTagLen = int(query(maxTagLen_sql)[0][0])
            distinctPid_sql = f"select distinct pid from prob_tag ;".replace('[', '').replace(
                ']', '')
            distinctPid = query(distinctPid_sql)
            maxPidLen = len(distinctPid)
            distinctPidArray = np.array(distinctPid).reshape(maxPidLen, 1)
            pidNTid = np.concatenate((distinctPidArray, np.zeros((maxPidLen, maxTagLen), dtype=int)), axis=1)

            for dpnt in pidNTid:
                cnt = 1
                for rpnt in prob_tag:
                    if rpnt[0] == dpnt[0]:
                        dpnt[cnt] = rpnt[1]
                        cnt += 1
            pidNTidDF = pd.DataFrame(pidNTid)
            pidNTidDF.columns = [f"tag{i}" for i in range(0, maxTagLen + 1)]
            tag_sql = f"select tid,tagName from tags where sid={selectedSubjectId};"
            tags = dict(query(tag_sql))
            tagDF = pidNTidDF.loc[:, [f"tag{i}" for i in range(1, maxTagLen + 1)]].replace(tags)
            pidNTidDF = pd.concat([pidNTidDF.loc[:, "tag0"], tagDF], axis=1)
            pidNTidDF = pidNTidDF.rename(columns={"tag0": "pid"})

            # 搜题
            searchIn = st.text_input("搜一下？输入单个连续关键字：")
            search_sql = f"select pid,bookName,page,num,content,remark,answer,star from problems INNER JOIN books on problems.bid=books.bid where concat_ws(pid,page,num,content,remark,answer,bookName) like '%{searchIn}%' and sid={selectedSubjectId};"
            problemSearched = query(search_sql)
            if problemSearched == ():
                st.info("什么都没找到")
            else:
                psdf = pd.DataFrame(problemSearched)
                psdf.columns = allColumns
                psdf = pd.merge(psdf, pidNTidDF, on="pid")
                AgGrid(psdf, columns_auto_size_mode=sa.ColumnsAutoSizeMode.FIT_CONTENTS, key=1)

            getStars_sql = f"select min(star),max(star) from problems where sid={selectedSubjectId}"
            starRange = query(getStars_sql)[0]
            minStar = int(starRange[0])
            maxStar = int(starRange[1])
            selectedStarRange = st.slider("按星星搜索？", minStar, maxStar + 1, (minStar, maxStar + 1))
            problemByStar_sql = f"select pid,bookName,page,num,content,remark,answer,star from problems INNER JOIN books on problems.bid=books.bid where star>={selectedStarRange[0]} and star<={selectedStarRange[1]}"
            problemByStar = query(problemByStar_sql)
            if problemByStar == ():
                st.info("什么都没找到")
            else:
                pbsdf = pd.DataFrame(problemByStar)
                pbsdf.columns = allColumns
                pbsdf = pd.merge(pbsdf, pidNTidDF, on="pid")
                AgGrid(pbsdf, columns_auto_size_mode=sa.ColumnsAutoSizeMode.FIT_CONTENTS, key=2)

            tag_sql = f"select tid,tagName from tags where sid={selectedSubjectId};"
            tags = query(tag_sql)
            if tags == ():
                st.info("一个tag都没有，快去管理tab添加")
            else:
                tags = dict(tags)
                selectedTags = st.multiselect("选择tag", [tag for tag in tags.values()])
                if selectedTags == []:
                    st.info("从下拉列表里选一个或多个tag吧")
                else:
                    selectedTagIds = [getKey(tags, tag) for tag in selectedTags]
                    problemIdsByTags_sql = f"select pid,tid from prob_tag where tid in ({selectedTagIds})".replace('[',
                                                                                                                   '').replace(
                        ']', '')
                    problemIdsByTags = query(problemIdsByTags_sql)
                    if problemIdsByTags == ():
                        st.info("所选tag下一个问题都没有")
                    else:
                        problemIdsByTags = list(problemIdsByTags)
                        maxTagLen_sql = f"select max(cnt) from (select count(tid) cnt from prob_tag where tid in ({selectedTagIds}) group by pid) a;".replace(
                            '[', '').replace(']', '')
                        maxTagLen = int(query(maxTagLen_sql)[0][0])
                        distinctPid_sql = f"select distinct pid from prob_tag where tid in ({selectedTagIds})".replace(
                            '[', '').replace(']', '')
                        distinctPid = query(distinctPid_sql)
                        maxPidLen = len(distinctPid)
                        distinctPidArray = np.array(distinctPid).reshape(maxPidLen, 1)
                        pidNTid = np.concatenate((distinctPidArray, np.zeros((maxPidLen, maxTagLen), dtype=int)),
                                                 axis=1)

                        for dpnt in pidNTid:
                            cnt = 1
                            for rpnt in problemIdsByTags:
                                if rpnt[0] == dpnt[0]:
                                    dpnt[cnt] = rpnt[1]
                                    cnt += 1
                        pidNTidDF = pd.DataFrame(pidNTid)
                        pidNTidDF.columns = [f"tag{i}" for i in range(0, maxTagLen + 1)]

                        tagDF = pidNTidDF.loc[:, [f"tag{i}" for i in range(1, maxTagLen + 1)]].replace(tags)
                        pidNTidDF = pd.concat([pidNTidDF.loc[:, "tag0"], tagDF], axis=1)
                        pidNTidDF = pidNTidDF.rename(columns={"tag0": "pid"})

                        problemsByTagDF = pd.merge(allProblemsDF, pidNTidDF, on="pid")
                        AgGrid(problemsByTagDF, columns_auto_size_mode=sa.ColumnsAutoSizeMode.FIT_CONTENTS, key=3)

            if st.button("显示全部"):
                allProblemsDF_t = pd.merge(allProblemsDF, pidNTidDF, on="pid")
                AgGrid(allProblemsDF_t, columns_auto_size_mode=sa.ColumnsAutoSizeMode.FIT_CONTENTS, key=4)

    if whatToDo == "管理":

        if st.button("显示所有tag"):
            sql = f"select tid,tagName from tags where sid={selectedSubjectId}"
            tags = query(sql)
            if tags == ():
                st.warning("还没tag呢，加点吧")
            else:
                df = pd.DataFrame(tags)
                df.columns = ["tid", "tagName"]
                AgGrid(df, key=5)
        newTag = st.text_input("添加新标签")
        addNewTag_sql = f"insert into tags (sid,tagName) values ({selectedSubjectId},'{newTag}')"
        if st.button("确定", key=1):
            try:
                cursor.execute(addNewTag_sql)
                db.commit()
                st.success("添加成功")
            except(Exception) as e:
                db.rollback()
                st.write(e)

        tagToDel = st.text_input("删除标签")
        delTag_sql = f"delete from tags where sid={selectedSubjectId} and tagName='{tagToDel}'"
        if st.button("确定", key=2):
            try:
                cursor.execute(delTag_sql)
                db.commit()
                st.success("删除成功")
            except(Exception) as e:
                db.rollback()
                st.write(e)

        if st.button("显示所有书"):
            sql = f"select bid,bookName from books;"
            books = query(sql)
            if books == ():
                st.warning("还没书呢，加点吧")
            else:
                df = pd.DataFrame(books)
                df.columns = ["bid", "bookName"]
                AgGrid(df, key=6)

        newBook = st.text_input("添加新书")
        addNewBook_sql = f"insert into books (bookName) values ('{newBook}')"
        if st.button("确定", key=3):
            try:
                cursor.execute(addNewBook_sql)
                db.commit()
                st.success("添加成功")
            except(Exception) as e:
                db.rollback()
                st.write(e)

        bookToDel = st.text_input("删除书")
        delBook_sql = f"delete from books where bookName='{bookToDel}'"
        if st.button("确定", key=4):
            try:
                cursor.execute(delBook_sql)
                db.commit()
                st.success("删除成功")
            except(Exception) as e:
                db.rollback()
                st.write(e)

        probToDel = st.text_input("删除题目编号")
        delProb_sql = f"delete from problems where pid={probToDel}"
        if st.button("确定", key=5):
            try:
                cursor.execute(delProb_sql)
                db.commit()
                st.success("删除成功")
            except(Exception) as e:
                db.rollback()
                st.write(e)

db.close()
