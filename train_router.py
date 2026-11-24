import csv

import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split

from cache import embed

rows = list(csv.DictReader(open("data/labels.csv")))
X = [embed(r["question"]) for r in rows]
y = [int(r["label"]) for r in rows]

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
clf = LogisticRegression(max_iter=1000).fit(X_train, y_train)
print(classification_report(y_test, clf.predict(X_test)))
joblib.dump(clf, "router.joblib")