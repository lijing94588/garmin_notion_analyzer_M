import main as m
def rows(sql,params=None):
 r=m.execute_d1_query(sql,params or []); return (r.get('result') or [{}])[0].get('results',[]) if r else []
def main():
 m.ensure_d1_schema(); tables=['garmin_raw_activities','garmin_raw_laps','garmin_raw_detail_json','garmin_running_analysis','garmin_weekly_running_analysis']
 print('=== Counts ===')
 for t in tables: print(t, rows(f'SELECT COUNT(*) AS n FROM {t}')[0]['n'])
 print('=== Date ranges ===')
 for t,c in [('garmin_raw_activities','start_date'),('garmin_raw_detail_json','start_date'),('garmin_running_analysis','date'),('garmin_weekly_running_analysis','week_start')]: print(t, rows(f'SELECT MIN({c}) AS min_date,MAX({c}) AS max_date FROM {t}')[0])
 print('=== Recent activities ==='); [print(x) for x in rows('SELECT activity_id,start_date,name,distance_km,avg_hr FROM garmin_raw_activities ORDER BY start_date DESC,activity_id DESC LIMIT 10')]
 print('=== Recent analysis ==='); [print(x) for x in rows('SELECT activity_id,date,distance_km,avg_hr,load_7d,load_28d,hr_decoupling_pct FROM garmin_running_analysis ORDER BY date DESC,activity_id DESC LIMIT 10')]
 print('=== Orphans ===')
 print('analysis without raw:',rows("SELECT r.activity_id FROM garmin_running_analysis r LEFT JOIN garmin_raw_activities a ON a.activity_id=r.activity_id WHERE a.activity_id IS NULL LIMIT 20"))
 print('raw without detail:',rows("SELECT a.activity_id FROM garmin_raw_activities a LEFT JOIN garmin_raw_detail_json d ON d.activity_id=a.activity_id WHERE d.activity_id IS NULL LIMIT 20"))
if __name__=='__main__': main()
