import sys
sys.path.append('.')
import app
df = app.get_dashboard_data('ACGRBR25.dbc')
print(df.columns.tolist())
