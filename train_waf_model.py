# train_waf_model.py
# Train a simple ML model to classify requests as benign or malicious
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import joblib

def main():
    # Load features
    df = pd.read_csv("waf_features.csv")
    print("Columns detected in waf_features.csv:", list(df.columns))
    # For demo: ask user to label some data
    if "label" not in df.columns:
        df["label"] = 0  # 0=benign, 1=malicious
        print("Please label your data in waf_features.csv (add a 'label' column: 0=benign, 1=malicious)")
        df.to_csv("waf_features.csv", index=False)
        return
    X = df.drop(["label", "user_agent", "client_ip", "method", "timestamp"], axis=1)
    y = df["label"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    clf = RandomForestClassifier(n_estimators=100, random_state=42)
    clf.fit(X_train, y_train)
    y_pred = clf.predict(X_test)
    print(classification_report(y_test, y_pred))
    joblib.dump(clf, "waf_model.joblib")
    print("Model saved as waf_model.joblib")

if __name__ == "__main__":
    main()
