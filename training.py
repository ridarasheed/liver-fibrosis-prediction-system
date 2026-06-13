import pandas as pd
import numpy as np
import joblib

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression

df = pd.read_csv("indian_liver_patient.csv")

df["Albumin_and_Globulin_Ratio"].fillna(
    df["Albumin_and_Globulin_Ratio"].median(),
    inplace=True
)

df["Dataset"] = df["Dataset"].map({1: 1, 2: 0})

X = df.drop("Dataset", axis=1)
y = df["Dataset"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y,
    test_size=0.2,
    random_state=42,
    stratify=y
)

scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)

lr = LogisticRegression(max_iter=1000)
lr.fit(X_train_scaled, y_train)

joblib.dump(lr, "lr_model.pkl")
joblib.dump(scaler, "scaler.pkl")

print("Model and Scaler file saved succesfully")