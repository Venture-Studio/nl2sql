import json
import os
from openai import OpenAI
import streamlit as st
from MySQLdb import _mysql
from MySQLdb.constants import FIELD_TYPE
import pandas as pd
import numpy as np
from dotenv import load_dotenv
import matplotlib.pyplot as plt


load_dotenv()

st.title("SQL Bot")
st.caption("A SQL chatbot")

if "messages" not in st.session_state:
    st.session_state["messages"] = [{"role": "assistant", "content": "Ask me questions about Employee Data! Try commands like \"Show me the tables\" and \"Show me the columns for table X\""}]

for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

if prompt := st.chat_input():

    client = OpenAI()
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)
    
    sql = 'NOTHING'
    with open('employees_structure.sql', 'r') as file:
        sql = file.read().replace('\n', '')

    prompt_system = f"""
    You are a master at SQL. 
    Your job is to write SQL queries to answer user requests. 
    Within the <ddl> tags is the SQL schema for a database. 
    Study it carefully in order to answer the user queries as accurately as possible. 
    Use all skills available to you to do this. 
    <ddl>{sql}</ddl>
    If necessary, you may break the response down into multiple steps for the user to execute.
    If you do not believe that the data exists to answer the user question, do not try. 
    Only write SQL that you believe execute within the provided DDL. 
    Ensure that your responses are compatible with MYSQL Global setting value ONLY_FULL_GROUP_BY.
    Strictly structure your responses to adhere to the following JSON structure:
    {{
      sql : [An array of SQL statements necessary to answer the user request. There should be 1 or more values in this list.]
      rationale : A string with your rationale for what you have provided.
      valid : A 1 if you believe the query can be run against the provided ddl or a 0 if you believe that the data does not exist.    
    }}
    """

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
          {
            "role": "system",
            "content": prompt_system
          },
          {
            "role": "user",
            "content": prompt
          }
        ],
        temperature=0,
        top_p=1,
        response_format={ "type": "json_object" }
      )


    response = response.choices[0].message.content
    try:
      response = json.loads(response)
    except:
      st.chat_message("assistant").write("Bad OpenAI Response:")  
      st.chat_message("assistant").write(response) 
      print(response.choices[0].message.content)
      exit()
       
    print(response)
    sql = response["sql"]
    rationale=response["rationale"]
    valid=response["valid"]
    
    if valid != 1:
      st.session_state.messages.append({"role": "assistant", "content": rationale})
      st.chat_message("assistant").write(rationale)

    else:
      st.session_state.messages.append({"role": "assistant", "content": rationale})
      st.chat_message("assistant").write(rationale)
      
      st.session_state.messages.append({"role": "assistant", "content": sql})
      st.chat_message("assistant").write(sql)  
      
      db = _mysql.connect(
        host=os.getenv("HOST"), 
        user=os.getenv("USERNAME"),
        password=os.getenv("PASSWORD"),
        database="employees",
        conv={
          FIELD_TYPE.LONG:str,
          FIELD_TYPE.INT24:str,
          FIELD_TYPE.DECIMAL:str,
          FIELD_TYPE.VARCHAR:str,
          FIELD_TYPE.DATE:str,
          FIELD_TYPE.DATETIME:str,
          FIELD_TYPE.VAR_STRING:str,
          FIELD_TYPE.FLOAT:str,
          FIELD_TYPE.BLOB:str,
          FIELD_TYPE.DOUBLE:str,
          FIELD_TYPE.BLOB:str,
          FIELD_TYPE.TINY_BLOB:str,
          FIELD_TYPE.LONG_BLOB:str,
          FIELD_TYPE.TINY:str,
          FIELD_TYPE.LONGLONG:str,
          FIELD_TYPE.MEDIUM_BLOB:str,
          FIELD_TYPE.NEWDECIMAL:str,
          FIELD_TYPE.ENUM:str,
          FIELD_TYPE.CHAR:str,
          FIELD_TYPE.SET:str
        }
      )

      db.query(sql[0])
      result=db.store_result()
      row_count = result.num_rows()
      column_count = result.num_fields()
      rows = result.fetch_row(maxrows=0,how=1)
      column_labels = []
      row_values = []
      row_limit = 100
      
      if row_count == 0:
        st.chat_message("assistant").write("Query returned but there is no data to report.")
      else:
        st.chat_message("assistant").write((f"Query returned with {row_count} row(s) and {column_count} column(s).") + (f" Showing top {row_limit} rows only." if row_count > row_limit else "")) 

      if row_count > 0:
        for i, x in enumerate(rows):
          if i >= row_limit:
            break
          
          print(x)
          row = []
          for k in x:
            if i == 0:
              # Get Column Labels
              column_labels.append(k)
            row.append(x[k])
          row_values.append(row)
        df = pd.DataFrame(row_values, columns=column_labels)
        st.session_state.messages.append({"role": "assistant", "content": df})
        st.chat_message("assistant").write(df)
        
        st.chat_message("assistant").write("Generating Image ... ")

        #Image Generation
        response = client.chat.completions.create(
          model="gpt-4o",
          messages=[
            {
              "role": "system",
              "content": "You are an expert at Matplotlib. You are also an expert in data visualization."
            },
            {
              "role": "user",
              "content": f"""Provide me with matplotlib parameters based on the three inputs that I give you. 
              First input is the request the user made. It will give you context on names and labels. 
              Second input is the data.
              Third input is the data labels.
              <request>{prompt}</request>
              <data>{row_values}</data>
              <labels>{column_labels}</labels>
              Respond back to me in JSON format with the following data attributes for Matplotlib:
              {{
                "labels": ["An array of labels"],
                "data": ["An array of the data values to be shown"],
                "xlabel": "The x label",
                "ylabel" : "The y label",
                "title": "The title"
              }}
              """ 
            }
          ],
          temperature=0.4,
          top_p=1,
          response_format={ "type": "json_object" }
        )
      
        response = response.choices[0].message.content
        
        try:
          response = json.loads(response)
          # Creating the histogram
          plt.figure(figsize=(10, 6))
          plt.bar(response["labels"], response["data"], color='blue')
          plt.xlabel(response["xlabel"])
          plt.ylabel(response["ylabel"])
          plt.title(response["title"])
          plt.xticks(rotation=45, ha='right')
          plt.tight_layout()

          # Display the plot
          st.pyplot(plt)
          plt.show()
          
        except Exception as e:
          print(e)
          st.chat_message("assistant").write("Bad OpenAI Response:")  
          st.chat_message("assistant").write(response) 
          print(response)
          exit()
