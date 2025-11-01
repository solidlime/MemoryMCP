#!/usr/bin/env python3
"""
Migrate all persona memories from SQLite to Qdrant
"""
import sqlite3
from pathlib import Path

# Import project modules
import config_utils
import persona_utils
import vector_utils

def main():
    config = config_utils.load_config()
    print("=" * 60)
    print(f"🎯 Target Qdrant: {config['qdrant_url']}")
    print(f"📁 Data directory: {config_utils.get_data_dir()}")
    print(f"📦 Storage backend: {config['storage_backend']}")
    print("=" * 60)
    
    # 各personaを移行
    personas = ['default', 'nilou', 'test']
    
    total_migrated = 0
    
    for persona in personas:
        print('\n' + '=' * 60)
        print(f'🔄 Migrating persona: {persona}')
        print('=' * 60)
        
        try:
            # personaを設定
            persona_utils.current_persona.set(persona)
            
            # SQLiteからデータを読み込み
            db_path = persona_utils.get_db_path(persona)
            if not Path(db_path).exists():
                print(f'⚠️  Database not found: {db_path}')
                continue
            
            # メモリ数を確認
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM memories')
                count = cursor.fetchone()[0]
            
            print(f'📊 Found {count} memories in SQLite: {db_path}')
            
            if count > 0:
                # Qdrantに移行
                result = vector_utils.migrate_sqlite_to_qdrant()
                print(f'✅ Migrated {result} memories to Qdrant')
                total_migrated += result
            else:
                print(f'ℹ️  No memories to migrate for {persona}')
                
        except Exception as e:
            print(f'❌ Error migrating {persona}: {e}')
            import traceback
            traceback.print_exc()
    
    print('\n' + '=' * 60)
    print(f'🎉 Migration complete! Total migrated: {total_migrated} memories')
    print('=' * 60)

if __name__ == '__main__':
    main()
