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
    if st.button("确定", key="sidebar_addSub_ok"):
        try:
            if subIn != '':
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
        if st.button("确定", key='addProb_addProb_ok'):
            if not (tagOK and bookOK):
                st.warning("还有东西没选呢吧，书或tag，添加了吗？学科选的对吗？")
            else:
                try:
                    getLastPid_sql = "select max(pid) from problems;"
                    addProb_sql = f"insert into problems (sid,bid,page,num,content,remark,answer,star) " \
                                  f"values ({selectedSubjectId},{selectedBookId},'{pageIn}','{numIn}','{contentIn}','{remarkIn}','{answerIn}',{int(starIn)});"
                    cursor.execute(addProb_sql)
                    db.commit()
                    lastPid = query(getLastPid_sql)[0][0]
                    for tagId in selectedTagIds:
                        addProbTag_sql = f"insert into prob_tag (pid,tid) values ({lastPid},{tagId});"
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

            if st.button("显示全部", key='getProb_showAll'):
                allProblemsDF_t = pd.merge(allProblemsDF, pidNTidDF, on="pid")
                AgGrid(allProblemsDF_t, columns_auto_size_mode=sa.ColumnsAutoSizeMode.FIT_CONTENTS, key=4)

    if whatToDo == "管理":

        st.write("========tag管理=========")

        if st.button("显示所有tag", key='manage_showAllTags'):
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
        if st.button("确定添加", key='manage_addTag_ok'):
            try:
                cursor.execute(addNewTag_sql)
                db.commit()
                st.success("添加成功")
            except(Exception) as e:
                db.rollback()
                st.write(e)

        tag_sql = f"select tid,tagName from tags where sid={selectedSubjectId};"
        tags = query(tag_sql)
        if tags == ():
            st.info("一个tag都没有，快去添加")
        else:
            tags = dict(tags)
            selectedTag = st.selectbox("修改标签：", [tag for tag in tags.values()])
            selectedTagId = getKey(tags, selectedTag)
            tagUpdated = st.text_input("tag修改为")
            updateTag_sql = f"update tags set tagName={tagUpdated} where sid={selectedSubjectId} and tid={selectedTagId}"
            if st.button("确定修改", key='manage_updateTag_ok'):
                try:
                    cursor.execute(updateTag_sql)
                    db.commit()
                    st.success("修改成功")
                except(Exception) as e:
                    db.rollback()
                    st.write(e)
            selectedTags = st.multiselect("选择tag", [tag for tag in tags.values()])
            selectedTagIds = [getKey(tags, tag) for tag in selectedTags]
            if st.button("确认删除", key='manage_delTag_ok'):
                delTag_sql = f"delete from tags where sid={selectedSubjectId} and tid in ({selectedTagIds})".replace(
                    ']', '').replace('[', '')
                delProbTag_Sql = f"delete from prob_tag where tid in ({selectedTagIds})".replace(']', '').replace('[',
                                                                                                                  '')
                try:
                    cursor.execute(delTag_sql)
                    cursor.execute(delProbTag_Sql)
                    db.commit()
                    st.success("删除成功")
                except(Exception) as e:
                    db.rollback()
                    st.write(e)

        # tagToUpdate=st.text_input("修改标签")
        #
        # tagToDel = st.text_input("删除标签")
        # getTag2delId_sql=f"select tid from tags where sid={selectedSubjectId} and tagName='{tagToDel}'"
        # delTag_sql = f"delete from tags where sid={selectedSubjectId} and tagName='{tagToDel}'"
        # if st.button("确定", key='manage_delTag_ok'):
        #     try:
        #         tag2delId=query(getTag2delId_sql)
        #
        #         cursor.execute(delTag_sql)
        #         delProbTag_Sql = f"delete from prob_tag where tid={}"
        #         db.commit()
        #         st.success("删除成功")
        #     except(Exception) as e:
        #         db.rollback()
        #         st.write(e)

        st.write("========书管理=========")

        if st.button("显示所有书", key='manage_showAllBooks'):
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
        if st.button("确定", key='manage_addBook_ok'):
            try:
                cursor.execute(addNewBook_sql)
                db.commit()
                st.success("添加成功")
            except(Exception) as e:
                db.rollback()
                st.write(e)

        book_sql = "SELECT bid,bookName FROM books;"
        books = query(book_sql)
        if books == ():
            st.info("一本书都没有，先去添加一本吧")
        else:
            books = dict(books)
            selectedBook = st.selectbox("修改书名：", [book for book in books.values()])
            selectedBookId = getKey(books, selectedBook)
            bookUpdated = st.text_input("书名修改为")
            updateBook_sql = f"update books set tagName={bookUpdated} where bid={selectedBookId}"
            if st.button("确定修改", key='manage_updateBook_ok'):
                try:
                    cursor.execute(updateBook_sql)
                    db.commit()
                    st.success("修改成功")
                except(Exception) as e:
                    db.rollback()
                    st.write(e)
            selectedBooks = st.multiselect("选择书", [book for book in books.values()])
            selectedBookIds = [getKey(books, book) for book in selectedBooks]
            st.warning("注意，删除书后，对应题目的书名将变为《未知书》，别忘了去修改")
            if st.button("确认删除", key='manage_delBook_ok'):
                delBook_sql = f"delete from books where bid in ({selectedBookIds})".replace(']', '').replace('[', '')
                updateProb_sql = f"update problems set bid=1 where bid in ({selectedBookIds})".replace(']', '').replace('[', '')
                try:
                    cursor.execute(delBook_sql)
                    cursor.execute(updateBook_sql)
                    db.commit()
                    st.success("删除成功")
                except(Exception) as e:
                    db.rollback()
                    st.write(e)

        # bookToDel = st.text_input("删除书")
        # delBook_sql = f"delete from books where bookName='{bookToDel}'"
        # if st.button("确定", key='manage_delBook_ok'):
        #     try:
        #         cursor.execute(delBook_sql)
        #         db.commit()
        #         st.success("删除成功")
        #     except(Exception) as e:
        #         db.rollback()
        #         st.write(e)

        st.write("========题目管理=========")

        probToDel = st.number_input("要删除的题目编号", value=0)
        delProb_sql = f"delete from problems where pid={probToDel}"
        delAlreadyTags_sql = f"delete from prob_tag where pid ={probToDel};"
        cursor.execute(delAlreadyTags_sql)
        if st.button("确定删除", key='manage_delProb_ok'):
            try:
                cursor.execute(delProb_sql)
                db.commit()
                st.success("删除成功")
            except(Exception) as e:
                db.rollback()
                st.write(e)

        idOfProbToUpdate = st.number_input("要修改的题目编号", value=0)
        probToUpdate_sql = f"select bookName,page,num,content,remark,answer,star from problems INNER JOIN books on problems.bid=books.bid where sid={selectedSubjectId} and pid={idOfProbToUpdate};"
        probToUpdate = query(probToUpdate_sql)
        if probToUpdate == ():
            st.info("没这题啊")
        else:
            probToUpdate = probToUpdate[0]
            book_sql = "SELECT bid,bookName FROM books;"
            books = query(book_sql)
            bookOK = 0
            if books == ():
                st.info("一本书都没有，先去管理tab添加一本吧")
            else:
                books = dict(books)
                selectedBook = st.selectbox("选择书", [book for book in books.values()], [probToUpdate[0]])
                selectedBookId = getKey(books, selectedBook)
                bookOK = 1
            pageIn = st.text_input("输入页码", value=probToUpdate[1])
            numIn = st.text_input("输入题号", value=probToUpdate[2])
            contentIn = st.text_area("输入题目", value=probToUpdate[3])
            remarkIn = st.text_area("输入评论", value=probToUpdate[4])
            answerIn = st.text_area("输入答案", value=probToUpdate[5])
            starIn = st.number_input("输入星级", value=probToUpdate[6])
            tag_sql = f"select tid,tagName from tags where sid={selectedSubjectId};"
            alreadyTags_sql = f"select tid from prob_tag where qid={idOfProbToUpdate};"
            tags = query(tag_sql)
            alreadyTags = query(tag_sql)
            tagOK = 0
            if tags == ():
                st.info("一个tag都没有，快去管理tab添加")
            else:
                tags = dict(tags)
                if alreadyTags == ():
                    selectedTags = st.multiselect("选择tag", [tag for tag in tags.values()])
                    selectedTagIds = [getKey(tags, tag) for tag in selectedTags]
                    tagOK = 1
                else:
                    selectedTags = st.multiselect("选择tag", [tag for tag in tags.values()],
                                                  [tags[at] for at in list(alreadyTags)])
                    selectedTagIds = [getKey(tags, tag) for tag in alreadyTags]
                    tagOK = 1
            if st.button("确定", key='manage_updateProb_ok'):
                if not (tagOK and bookOK):
                    st.warning("还有东西没选呢吧，书或tag，添加了吗？学科选的对吗？")
                else:
                    try:
                        updateProb_sql = f"update problems set bid={selectedBookId},page='{pageIn}',num='{numIn}',content='{contentIn}',remark='{remarkIn}',answer='{answerIn}',star={int(starIn)});"
                        cursor.execute(updateProb_sql)
                        delAlreadyTags_sql = f"delete from prob_tag where pid = {idOfProbToUpdate};"
                        cursor.execute(delAlreadyTags_sql)
                        for tagId in selectedTagIds:
                            addProbTag_sql = f"insert into prob_tag (pid,tid) values ({idOfProbToUpdate},{tagId});"
                            cursor.execute(addProbTag_sql)
                        db.commit()
                        st.success("修改成功")
                    except(Exception) as e:
                        db.rollback()
                        st.warning("没有修改成功")
                        st.write(e)

db.close()
