import chromadb
from chromadb.utils import embedding_functions
import os
import logging
import pandas as pd
from dotenv import load_dotenv
from pprint import pprint



load_dotenv()
client = chromadb.PersistentClient(path="eventdb")

# Creating a DataFrame to store descriptions and their ids
# df_db = pd.DataFrame(columns=["ids","description"])
# df_db.to_csv("eventdb/df_db.csv")
df_db = pd.read_csv("eventdb/df_db.csv")

def add_to_db(description: str, path: str):
    collection = client.get_or_create_collection(name="eventdb")

    # Adding descriptions to a dataframe to have the ids stored
    df_db = pd.read_csv(path)
    df_db.loc[len(df_db)] = {"ids": f"id{len(df_db)+1}", "description": description}
    df_db.to_csv(path, index=False)

    # Adding the description as a new document
    collection.add(
        documents=[
            df_db.iloc[len(df_db) - 1]["description"],
        ],
        ids=[f"id{len(df_db)}"]
    )

    return collection


def update_to_db(description: str, path: str, message: str):
    collection = client.get_or_create_collection(name="eventdb")
    similar_record = collection.query(
        query_texts=description,
        n_results=1
    )
    db_id = str(similar_record["ids"][0][0])

    collection.update(
        ids=[db_id],
        documents=[message]
    )

    df_db = pd.read_csv(path)
    df_db.loc[df_db["ids"] == db_id, "description"] = message
    df_db.to_csv(path, index=False)
    return collection

collection = client.get_or_create_collection(name="eventdb")

# similar_record = collection.query(
#         query_texts="Can you move the team meeting with Alice and Bob to next Wednesday at 3pm instead?",
#         n_results=1
#     )
# print(similar_record["documents"][0][0])
# collection.add(
#     documents=[
#         "Created new event with the name 'Team Meeting' with Calendar_ID=p3omdijoqei2dv3r1lmos4op98 starting at 2025-06-03 14:00 with participant(s) Alice, Bob",
#     ],
#     ids=["id1"]
# )
# collection = client.get_or_create_collection(name="eventdb")
# query = "Can you move the team meeting with Alice and Bob to next Wednesday at 3pm instead?"
# update_to_db(query, "eventdb/df_db.csv", "Change the time of \"Team Meeting\" from 2025-06-03 14:00 to 2025-06-04 with Calendar_ID=sdfjhasd23424;aschlfgk")
# add_to_db(description="Created new event with the name 'Team Meeting' with Calendar_ID=p3omdijoqei2dv3r1lmos4op98 starting at 2025-06-03 14:00 with participant(s) Alice, Bob", path="eventdb/df_db.csv")
# collection.delete(ids=["id3"])
# print(collection.get())

