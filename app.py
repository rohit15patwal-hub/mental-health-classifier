# ============================================================
# app.py — Flask backend with SQLite database
# ============================================================


from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import pickle
import pandas as pd
import sqlite3
from datetime import datetime

app = Flask(__name__)
CORS(app)

# ── Load ML model ─────────────────────────────────────────────
with open('mental_health_model.pkl', 'rb') as f:
    model = pickle.load(f)
with open('label_encoder.pkl', 'rb') as f:
    le = pickle.load(f)
with open('feature_columns.pkl', 'rb') as f:
    feature_cols = pickle.load(f)

print("✅ Model loaded — MindScan ready at http://localhost:5000")

# ── Conversion maps ───────────────────────────────────────────
FREQ_MAP    = {'Seldom':0,'Sometimes':1,'Usually':2,'Most-Often':3}
YES_NO_MAP  = {'Seldom':0,'Sometimes':0,'Usually':1,'Most-Often':1}
RATING_MAP  = {'Seldom':2,'Sometimes':4,'Usually':6,'Most-Often':8}

FREQ_COLS   = ['Sadness','Euphoric','Exhausted','Sleep dissorder']
YES_NO_COLS = ['Mood Swing','Suicidal thoughts','Anorxia',
               'Authority Respect','Aggressive Response',
               'Ignore & Move-On','Admit Mistakes','Overthinking',
               'Nervous Break-down','Try-Explanation']
RATING_COLS = ['Sexual Activity','Concentration','Optimisim']

# ── Database helper ───────────────────────────────────────────
def get_db():
    """Opens a database connection and returns conn and cursor"""
    conn   = sqlite3.connect('database.db')
    # row_factory lets us access columns by name like a dictionary
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    return conn, cursor


# ══════════════════════════════════════════════════════════════
# ROUTES
# ══════════════════════════════════════════════════════════════

# ── Homepage ──────────────────────────────────────────────────
@app.route('/')
def home():
    return render_template('index.html')


# ── Save user info before assessment ─────────────────────────
# Called when user submits their name/age/gender form

@app.route('/register', methods=['POST'])
def register():
    data   = request.get_json()
    name   = data.get('name', '').strip()
    age    = data.get('age', 0)
    gender = data.get('gender', '').strip()

    if not name or not age or not gender:
        return jsonify({'error': 'Please fill all fields'}), 400

    try:                                          # ← ADD try/except
        conn, cursor = get_db()
        cursor.execute('''
            INSERT INTO users (name, age, gender, created_at)
            VALUES (?, ?, ?, ?)
        ''', (name, int(age), gender,
              datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        print(f"✅ New user registered: {name} (id={user_id})")
        return jsonify({'user_id': user_id, 'name': name})

    except Exception as e:                        # ← catches DB errors
        print(f"❌ Register error: {e}")
        return jsonify({'error': str(e)}), 500    # ← returns readable JSON

# ── Predict + save to database ────────────────────────────────
@app.route('/predict', methods=['POST'])
def predict():
    data    = request.get_json()
    user_id = data.get('user_id')
    answers = data.get('answers', {})

    # Convert answers using correct maps
    converted = {}
    for col, val in answers.items():
        if col in FREQ_COLS:
            converted[col] = FREQ_MAP[val]
        elif col in YES_NO_COLS:
            converted[col] = YES_NO_MAP[val]
        else:
            converted[col] = RATING_MAP[val]

    # Run ML model
    input_df   = pd.DataFrame([converted])[feature_cols]
    pred_num   = model.predict(input_df)[0]
    condition  = le.inverse_transform([pred_num])[0]
    probs      = model.predict_proba(input_df)[0]
    confidence = round(float(probs[pred_num]) * 100, 1)

    prob_dict = {
        le.classes_[i]: round(float(probs[i]) * 100, 1)
        for i in range(len(le.classes_))
    }

    # Save assessment to database
    conn, cursor = get_db()

    cursor.execute('''
        INSERT INTO assessments
        (user_id, condition, confidence, bipolar1_prob,
         bipolar2_prob, depression_prob, normal_prob, taken_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_id,
        condition,
        confidence,
        prob_dict.get('Bipolar Type-1', 0),
        prob_dict.get('Bipolar Type-2', 0),
        prob_dict.get('Depression', 0),
        prob_dict.get('Normal', 0),
        datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ))

    assessment_id = cursor.lastrowid

    # Save all 17 responses
    cursor.execute('''
        INSERT INTO responses
        (assessment_id, sadness, euphoric, exhausted,
         sleep_disorder, mood_swing, suicidal_thoughts,
         anorexia, authority_respect, aggressive_response,
         ignore_moveon, admit_mistakes, overthinking,
         nervous_breakdown, try_explanation,
         sexual_activity, concentration, optimism)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ''', (
        assessment_id,
        answers.get('Sadness'),
        answers.get('Euphoric'),
        answers.get('Exhausted'),
        answers.get('Sleep dissorder'),
        answers.get('Mood Swing'),
        answers.get('Suicidal thoughts'),
        answers.get('Anorxia'),
        answers.get('Authority Respect'),
        answers.get('Aggressive Response'),
        answers.get('Ignore & Move-On'),
        answers.get('Admit Mistakes'),
        answers.get('Overthinking'),
        answers.get('Nervous Break-down'),
        answers.get('Try-Explanation'),
        answers.get('Sexual Activity'),
        answers.get('Concentration'),
        answers.get('Optimisim')
    ))

    conn.commit()
    conn.close()

    print(f"✅ Assessment saved for user_id={user_id} → {condition} ({confidence}%)")

    return jsonify({
        'condition':     condition,
        'confidence':    confidence,
        'probabilities': prob_dict
    })


# ── History page ──────────────────────────────────────────────
# Shows all past assessments in a table
@app.route('/history')
def history():
    conn, cursor = get_db()

    # JOIN users and assessments tables to get full info
    # JOIN means combine rows from two tables where user_id matches
    cursor.execute('''
        SELECT
            u.name,
            u.age,
            u.gender,
            a.condition,
            a.confidence,
            a.taken_at
        FROM assessments a
        JOIN users u ON a.user_id = u.id
        ORDER BY a.taken_at DESC
    ''')
    # ORDER BY taken_at DESC → newest first

    records = cursor.fetchall()
    conn.close()

    return render_template('history.html', records=records)


# ── Stats page ────────────────────────────────────────────────
# Shows overall statistics across all assessments
@app.route('/stats')
def stats():
    conn, cursor = get_db()

    # Total assessments
    cursor.execute("SELECT COUNT(*) FROM assessments")
    total = cursor.fetchone()[0]

    # Count per condition
    cursor.execute('''
        SELECT condition, COUNT(*) as count
        FROM assessments
        GROUP BY condition
        ORDER BY count DESC
    ''')
    condition_counts = cursor.fetchall()

    # Average confidence
    cursor.execute("SELECT ROUND(AVG(confidence), 1) FROM assessments")
    avg_conf = cursor.fetchone()[0]

    # Most recent 5 assessments
    cursor.execute('''
        SELECT u.name, a.condition, a.confidence, a.taken_at
        FROM assessments a
        JOIN users u ON a.user_id = u.id
        ORDER BY a.taken_at DESC
        LIMIT 5
    ''')
    recent = cursor.fetchall()

    conn.close()

    return render_template('stats.html',
                           total=total,
                           condition_counts=condition_counts,
                           avg_conf=avg_conf,
                           recent=recent)

def init_db():
    conn, cursor = get_db()
    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT    NOT NULL,
            age        INTEGER NOT NULL,
            gender     TEXT    NOT NULL,
            created_at TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS assessments (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL,
            condition     TEXT    NOT NULL,
            confidence    REAL    NOT NULL,
            bipolar1_prob REAL,
            bipolar2_prob REAL,
            depression_prob REAL,
            normal_prob   REAL,
            taken_at      TEXT    NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS responses (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            assessment_id       INTEGER NOT NULL,
            sadness             TEXT,
            euphoric            TEXT,
            exhausted           TEXT,
            sleep_disorder      TEXT,
            mood_swing          TEXT,
            suicidal_thoughts   TEXT,
            anorexia            TEXT,
            authority_respect   TEXT,
            aggressive_response TEXT,
            ignore_moveon       TEXT,
            admit_mistakes      TEXT,
            overthinking        TEXT,
            nervous_breakdown   TEXT,
            try_explanation     TEXT,
            sexual_activity     TEXT,
            concentration       TEXT,
            optimism            TEXT,
            FOREIGN KEY (assessment_id) REFERENCES assessments(id)
        );
    ''')
    conn.commit()
    conn.close()
    print("✅ Database initialized")

if __name__ == '__main__':
    init_db()
    app.run(debug=True)