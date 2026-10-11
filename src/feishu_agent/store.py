import sqlite3,json,time,threading,pathlib,uuid

class Store:
    def __init__(self, directory):
        pathlib.Path(directory).mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(str(pathlib.Path(directory)/"communication.sqlite3"),check_same_thread=False,isolation_level=None)
        self.db.row_factory=sqlite3.Row;self.lock=threading.RLock()
        self.db.executescript("""PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL;
        CREATE TABLE IF NOT EXISTS deliveries(key TEXT PRIMARY KEY,fingerprint TEXT,state TEXT,result TEXT);
        CREATE TABLE IF NOT EXISTS inbox(id TEXT PRIMARY KEY,payload TEXT,state TEXT,updated REAL);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT);
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,time REAL,kind TEXT,detail TEXT);
        """)
    def recover(self):
        # Call only after acquiring the exclusive service lock.
        self.db.execute("UPDATE inbox SET state='interrupted' WHERE state='running'")

    def reserve(self,key,fingerprint):
        with self.lock:
            row=self.db.execute("SELECT * FROM deliveries WHERE key=?",(key,)).fetchone()
            if row:
                if row['fingerprint']!=fingerprint:raise ValueError("IDEMPOTENCY_KEY_CONFLICT")
                if row['state']=='completed':return json.loads(row['result'])
                raise ValueError("DELIVERY_UNCERTAIN_DO_NOT_RESEND")
            self.db.execute("INSERT INTO deliveries VALUES(?,?,?,NULL)",(key,fingerprint,'started'))
            return None

    def delivered(self,key,result):
        with self.lock:self.db.execute("UPDATE deliveries SET state='completed',result=? WHERE key=?",(json.dumps(result),key))

    def enqueue(self,id,payload,state='queued'):
        with self.lock:return bool(self.db.execute("INSERT OR IGNORE INTO inbox VALUES(?,?,?,?)",(id,json.dumps(payload,ensure_ascii=False),state,time.time())).rowcount)

    def claim(self):
        with self.lock:
            row=self.db.execute("SELECT * FROM inbox WHERE state='queued' ORDER BY updated LIMIT 1").fetchone()
            if not row:return None
            self.db.execute("UPDATE inbox SET state='running',updated=? WHERE id=?",(time.time(),row['id']))
            return row['id'],json.loads(row['payload'])

    def finish(self,id,state='completed'):
        with self.lock:self.db.execute("UPDATE inbox SET state=?,updated=? WHERE id=?",(state,time.time(),id))

    def get(self,key,default=None):
        with self.lock:row=self.db.execute("SELECT value FROM settings WHERE key=?",(key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set(self,key,value):
        with self.lock:self.db.execute("INSERT OR REPLACE INTO settings VALUES(?,?)",(key,json.dumps(value)))

    def session(self):
        sid=self.get('session')
        if not sid:sid='feishu-'+uuid.uuid4().hex;self.set('session',sid)
        return sid

    def event(self,kind,detail):
        with self.lock:self.db.execute("INSERT INTO events(time,kind,detail) VALUES(?,?,?)",(time.time(),kind,json.dumps(detail,ensure_ascii=False)))
