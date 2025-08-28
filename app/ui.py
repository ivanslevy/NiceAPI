from nicegui import ui, app
from urllib.parse import urlparse
from sqlalchemy.orm import Session
from fastapi import Depends
import requests
import asyncio
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from .database import SessionLocal, get_db
from . import crud, models, schemas
from .language import get_text

# Load environment variables
load_dotenv()
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "password")

def create_ui():

    @ui.page('/')
    def main_page(db: Session = Depends(get_db)):
        ui.add_head_html('''
            <style>
            .custom-scrollbar::-webkit-scrollbar { width: 8px; }
            .custom-scrollbar::-webkit-scrollbar-thumb { background: white; border-radius: 4px; }
            .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
            .custom-scrollbar { scrollbar-width: thin; scrollbar-color: white transparent; }
            .q-dialog__backdrop {
                background: rgba(0, 0, 0, 0.8) !important;
            }
            </style>
        ''')
        @asynccontextmanager
        async def loading_animation():
            with ui.dialog() as dialog, ui.card().classes('bg-transparent shadow-none'):
                ui.spinner('puff', color='white', size='xl')
            
            dialog.open()
            dialog.props('persistent')
            try:
                await asyncio.sleep(0.05) # time for dialog to show
                yield
                await asyncio.sleep(0.3) # user-requested delay
            finally:
                dialog.close()

        # If the user is not authenticated, redirect to the login page.
        ui.colors(
            primary='#2F6BFF',
            secondary='#5C8FFF',
            accent='#14B8A6',
            positive='#10B981',
            negative='#EF4444',
            info='#3B82F6',
            warning='#F59E0B'
        )
        if app.storage.user.get('authenticated', False):
            # This is the main content of the application.
            # It's only shown if the user is authenticated.
            
            def get_all_providers_as_dict():
                providers = crud.get_providers(db)
                return [
                    {key: getattr(p, key) for key in p.__table__.columns.keys()}
                    for p in providers
                ]

            def refresh_providers_table():
                table.rows = get_all_providers_as_dict()
                table.update()

            with ui.header(elevated=True).style('background-color: #111827').classes('p-2'):
                with ui.column().classes('w-full gap-0'):
                    ui.label(get_text('api_management')).classes('text-h5 self-start')
                    
                    def logout():
                        app.storage.user['authenticated'] = False
                        ui.navigate.reload()

                    def set_language(lang: str):
                        app.storage.user['lang'] = lang
                        ui.navigate.reload()

                    with ui.row().classes('w-full items-center no-wrap'):
                        with ui.element('div').classes('flex-grow overflow-x-auto whitespace-nowrap py-1'):
                            with ui.tabs() as tabs:
                                dashboard_tab = ui.tab(get_text('dashboard'))
                                providers_tab = ui.tab(get_text('providers'))
                                groups_tab = ui.tab(get_text('groups'))
                                logs_tab = ui.tab(get_text('call_logs'))
                                errors_tab = ui.tab(get_text('failure_keywords'))
                                api_keys_tab = ui.tab(get_text('api_keys'))
                                settings_tab = ui.tab(get_text('settings'))
                        ui.space()
                        with ui.button(icon='language').props('flat text-color="white"'):
                            with ui.menu():
                                ui.menu_item('English', on_click=lambda: set_language('en'))
                                ui.menu_item('中文(简体)', on_click=lambda: set_language('zh-CN'))
                                ui.menu_item('中文(繁體)', on_click=lambda: set_language('zh-TW'))
                                ui.menu_item('한국어', on_click=lambda: set_language('ko'))
                                ui.menu_item('日本語', on_click=lambda: set_language('ja'))
                        ui.button(get_text('logout'), on_click=logout).props('flat text-color="white"')


            with ui.tab_panels(tabs, value=dashboard_tab).classes('w-full'):
                with ui.tab_panel(dashboard_tab):
                    def build_dashboard(container):
                        with container:
                            with ui.element('div').classes('flex flex-wrap w-full gap-4'):
                                # Chart 1: Model Usage Distribution
                                with ui.element('div').classes('w-full sm:w-[calc(50%-0.5rem)] border rounded-lg p-4 shadow-md bg-white'):
                                    ui.label(get_text('model_usage_distribution')).classes('text-h6')
                                    with ui.element('div').classes('w-full h-64'):
                                        db.expire_all()
                                        logs = crud.get_call_logs(db, limit=1000)
                                        model_counts = {}
                                        for log in logs:
                                            if log.provider and log.provider.model:
                                                model_name = log.provider.model
                                                model_counts[model_name] = model_counts.get(model_name, 0) + 1
                                        
                                        chart_data = [{'name': k, 'value': v} for k,v in model_counts.items()]
                                        if chart_data:
                                            ui.echart({
                                                'tooltip': {'trigger': 'item'},
                                                'legend': {'orient': 'vertical', 'left': 'left'},
                                                'color': ['#2F6BFF', '#14B8A6', '#3B82F6', '#5C8FFF', '#F59E0B', '#6B7280'],
                                                'series': [{
                                                    'name': get_text('api_calls'),
                                                    'type': 'pie',
                                                    'radius': '70%',
                                                    'data': chart_data,
                                                    'emphasis': {
                                                        'itemStyle': {
                                                            'shadowBlur': 10,
                                                            'shadowOffsetX': 0,
                                                            'shadowColor': 'rgba(0, 0, 0, 0.5)'
                                                        }
                                                    }
                                                }]
                                            })
                                        else:
                                            ui.label(get_text('no_api_call_data')).classes('flex-center')

                                # Chart 2: Daily API Calls
                                with ui.element('div').classes('w-full sm:w-[calc(50%-0.5rem)] border rounded-lg p-4 shadow-md bg-white'):
                                    ui.label(get_text('daily_api_calls')).classes('text-h6')
                                    with ui.element('div').classes('w-full h-64'):
                                        from datetime import datetime, timedelta
                                        import pytz

                                        TAIPEI_TZ = pytz.timezone('Asia/Taipei')
                                        logs = crud.get_call_logs(db, limit=5000) # Fetch more for historical data
                                        daily_counts = {}
                                        for i in range(7):
                                            date = (datetime.now(TAIPEI_TZ) - timedelta(days=i)).strftime('%Y-%m-%d')
                                            daily_counts[date] = 0
                                        
                                        for log in logs:
                                            date_str = log.request_timestamp.astimezone(TAIPEI_TZ).strftime('%Y-%m-%d')
                                            if date_str in daily_counts:
                                                daily_counts[date_str] += 1
                                        
                                        sorted_dates = sorted(daily_counts.keys())
                                        chart_data = [daily_counts[d] for d in sorted_dates]

                                        if any(c > 0 for c in chart_data):
                                            ui.echart({
                                                'xAxis': {'type': 'category', 'data': sorted_dates},
                                                'yAxis': {'type': 'value'},
                                                'series': [{'data': chart_data, 'type': 'bar', 'itemStyle': {'color': '#2F6BFF'}}]
                                            })
                                        else:
                                            ui.label(get_text('no_recent_api_call_data')).classes('flex-center')

                                # Chart 3: API Call Success Rate
                                with ui.element('div').classes('w-full sm:w-[calc(50%-0.5rem)] border rounded-lg p-4 shadow-md bg-white'):
                                    ui.label(get_text('api_call_success_rate')).classes('text-h6')
                                    with ui.element('div').classes('w-full h-64'):
                                        logs = crud.get_call_logs(db, limit=1000)
                                        success_count = sum(1 for log in logs if log.is_success)
                                        failure_count = len(logs) - success_count
                                        
                                        if logs:
                                            ui.echart({
                                                'tooltip': {'trigger': 'item'},
                                                'legend': {'top': '5%', 'left': 'center'},
                                                'color': ['#10B981', '#EF4444'],
                                                'series': [{
                                                    'name': get_text('api_call_success_rate'),
                                                    'type': 'pie',
                                                    'radius': ['40%', '70%'],
                                                    'avoidLabelOverlap': False,
                                                    'label': {'show': False, 'position': 'center'},
                                                    'emphasis': {'label': {'show': True, 'fontSize': '20', 'fontWeight': 'bold'}},
                                                    'labelLine': {'show': False},
                                                    'data': [
                                                        {'value': success_count, 'name': get_text('successful')},
                                                        {'value': failure_count, 'name': get_text('failed')}
                                                    ]
                                                }]
                                            })
                                        else:
                                            ui.label(get_text('no_api_call_data')).classes('flex-center')

                                # Chart 4: Average Response Time by Model
                                with ui.element('div').classes('w-full sm:w-[calc(50%-0.5rem)] border rounded-lg p-4 shadow-md bg-white'):
                                    ui.label(get_text('avg_response_time_ms')).classes('text-h6')
                                    with ui.element('div').classes('w-full h-64'):
                                        logs = crud.get_call_logs(db, limit=100) # Analyze recent calls
                                        model_times = {}
                                        model_counts = {}
                                        for log in logs:
                                            if log.is_success and log.response_time_ms is not None:
                                                model = log.provider.model
                                                model_times[model] = model_times.get(model, 0) + log.response_time_ms
                                                model_counts[model] = model_counts.get(model, 0) + 1
                                        
                                        avg_times = {m: model_times[m]/model_counts[m] for m in model_times}
                                        sorted_models = sorted(avg_times.keys())
                                        chart_data = [round(avg_times[m]) for m in sorted_models]

                                        if chart_data:
                                            ui.echart({
                                                'xAxis': {'type': 'category', 'data': sorted_models, 'axisLabel': {'interval': 0, 'rotate': 30}},
                                                'yAxis': {'type': 'value'},
                                                'series': [{'data': chart_data, 'type': 'bar', 'itemStyle': {'color': '#2F6BFF'}}],
                                                'tooltip': {'trigger': 'axis'}
                                            })
                                        else:
                                            ui.label(get_text('no_successful_calls_with_response_time')).classes('flex-center')
                                
                                # Chart 5: API Endpoint Success Rate
                                with ui.element('div').classes('w-full sm:w-[calc(50%-0.5rem)] border rounded-lg p-4 shadow-md bg-white'):
                                    ui.label(get_text('api_endpoint_success_rate')).classes('text-h6')
                                    with ui.element('div').classes('w-full h-64'):
                                        logs = crud.get_call_logs(db, limit=1000)
                                        endpoint_stats = {}
                                        for log in logs:
                                            if log.provider:
                                                try:
                                                    # Parse the URL and get the netloc (domain)
                                                    parsed_url = urlparse(log.provider.api_endpoint)
                                                    endpoint = parsed_url.netloc
                                                except Exception:
                                                    endpoint = log.provider.api_endpoint # Fallback

                                                if endpoint not in endpoint_stats:
                                                    endpoint_stats[endpoint] = {'success': 0, 'total': 0}
                                                endpoint_stats[endpoint]['total'] += 1
                                                if log.is_success:
                                                    endpoint_stats[endpoint]['success'] += 1
                                        
                                        endpoint_rates = {e: (s['success']/s['total'])*100 for e, s in endpoint_stats.items() if s['total'] > 0}
                                        sorted_endpoints = sorted(endpoint_rates.keys())
                                        chart_data = [round(endpoint_rates[e]) for e in sorted_endpoints]

                                        if chart_data:
                                            ui.echart({
                                                'xAxis': {'type': 'category', 'data': sorted_endpoints, 'axisLabel': {'interval': 0, 'rotate': 15}},
                                                'yAxis': {'type': 'value', 'min': 0, 'max': 100, 'axisLabel': {'formatter': '{value} %'}},
                                                'series': [{'data': chart_data, 'type': 'bar', 'itemStyle': {'color': '#2F6BFF'}}],
                                                'tooltip': {'trigger': 'axis', 'formatter': '{b}: {c}%'}
                                            })
                                        else:
                                            ui.label(get_text('no_data_for_endpoint_success_rate')).classes('flex-center')

                                # Chart 6: Average Response Time by Endpoint
                                with ui.element('div').classes('w-full sm:w-[calc(50%-0.5rem)] border rounded-lg p-4 shadow-md bg-white'):
                                    ui.label(get_text('avg_response_time_by_endpoint_ms')).classes('text-h6')
                                    with ui.element('div').classes('w-full h-64'):
                                        logs = crud.get_call_logs(db, limit=1000)
                                        endpoint_times = {}
                                        endpoint_counts = {}
                                        for log in logs:
                                            if log.provider and log.is_success and log.response_time_ms is not None:
                                                try:
                                                    # Parse the URL and get the netloc (domain)
                                                    parsed_url = urlparse(log.provider.api_endpoint)
                                                    endpoint = parsed_url.netloc
                                                except Exception:
                                                    endpoint = log.provider.api_endpoint # Fallback
                                                    
                                                endpoint_times[endpoint] = endpoint_times.get(endpoint, 0) + log.response_time_ms
                                                endpoint_counts[endpoint] = endpoint_counts.get(endpoint, 0) + 1
                                        
                                        avg_times = {e: endpoint_times[e]/endpoint_counts[e] for e in endpoint_times}
                                        sorted_endpoints = sorted(avg_times.keys())
                                        chart_data = [round(avg_times[e]) for e in sorted_endpoints]

                                        if chart_data:
                                            ui.echart({
                                                'xAxis': {'type': 'category', 'data': sorted_endpoints, 'axisLabel': {'interval': 0, 'rotate': 15}},
                                                'yAxis': {'type': 'value'},
                                                'series': [{'data': chart_data, 'type': 'bar', 'itemStyle': {'color': '#2F6BFF'}}],
                                                'tooltip': {'trigger': 'axis'}
                                            })
                                        else:
                                            ui.label(get_text('no_successful_calls_with_response_time')).classes('flex-center')
                               
                                # Chart 7: Total API Calls by Endpoint
                                with ui.element('div').classes('w-full sm:w-[calc(50%-0.5rem)] border rounded-lg p-4 shadow-md bg-white'):
                                    ui.label(get_text('total_api_calls_by_endpoint')).classes('text-h6')
                                    with ui.element('div').classes('w-full h-64'):
                                        logs = crud.get_call_logs(db, limit=1000)
                                        endpoint_counts = {}
                                        for log in logs:
                                            if log.provider:
                                                try:
                                                    parsed_url = urlparse(log.provider.api_endpoint)
                                                    endpoint = parsed_url.netloc
                                                except Exception:
                                                    endpoint = log.provider.api_endpoint # Fallback
                                                
                                                endpoint_counts[endpoint] = endpoint_counts.get(endpoint, 0) + 1

                                        sorted_endpoints = sorted(endpoint_counts.keys())
                                        chart_data = [endpoint_counts[e] for e in sorted_endpoints]

                                        if chart_data:
                                            ui.echart({
                                                'xAxis': {'type': 'category', 'data': sorted_endpoints, 'axisLabel': {'interval': 0, 'rotate': 15}},
                                                'yAxis': {'type': 'value'},
                                                'series': [{'data': chart_data, 'type': 'bar', 'itemStyle': {'color': '#2F6BFF'}}],
                                                'tooltip': {'trigger': 'axis'}
                                            })
                                        else:
                                            ui.label(get_text('no_api_call_data')).classes('flex-center')
                                
                                # Chart 8: Total Cost by Model
                                with ui.element('div').classes('w-full sm:w-[calc(50%-0.5rem)] border rounded-lg p-4 shadow-md bg-white'):
                                    ui.label(get_text('total_cost_by_model')).classes('text-h6')
                                    with ui.element('div').classes('w-full h-64'):
                                        logs = crud.get_call_logs(db, limit=1000)
                                        model_costs = {}
                                        for log in logs:
                                            if log.provider and log.provider.model and log.cost is not None:
                                                model_name = log.provider.model
                                                model_costs[model_name] = model_costs.get(model_name, 0) + log.cost
                                        
                                        sorted_models = sorted(model_costs.keys())
                                        chart_data = [round(model_costs[m], 4) for m in sorted_models]

                                        if chart_data:
                                            ui.echart({
                                                'xAxis': {'type': 'category', 'data': sorted_models, 'axisLabel': {'interval': 0, 'rotate': 30}},
                                                'yAxis': {'type': 'value'},
                                                'series': [{'data': chart_data, 'type': 'bar', 'itemStyle': {'color': '#2F6BFF'}}],
                                                'tooltip': {'trigger': 'axis', 'formatter': '{b}: ${c}'}
                                            })
                                        else:
                                            ui.label(get_text('no_cost_data')).classes('flex-center')

                    async def refresh_dashboard():
                        async with loading_animation():
                            dashboard_container.clear()
                            build_dashboard(dashboard_container)
                        ui.notify(get_text('dashboard_refreshed'), color='positive')

                    with ui.row().classes('w-full items-center mb-4'):
                        ui.label(get_text('dashboard')).classes('text-h6')
                        ui.space()
                        ui.button(get_text('refresh_data'), on_click=refresh_dashboard, icon='refresh', color='primary').props('flat')
                    dashboard_container = ui.element('div').classes('w-full')
                    build_dashboard(dashboard_container)

                with ui.tab_panel(providers_tab):
                    async def refresh_providers_table_async():
                        async with loading_animation():
                            table.update_rows(get_all_providers_as_dict())
                        ui.notify(get_text('providers_refreshed'), color='positive')

                    with ui.row().classes('w-full items-center mb-4'):
                        ui.label(get_text('providers')).classes('text-h6')
                        ui.space()
                        ui.button(get_text('refresh_providers'), on_click=refresh_providers_table_async, icon='refresh', color='primary').props('flat')

                    # Add Provider Dialog
                    with ui.dialog() as add_dialog, ui.card().style('width: 60vw; max-width: 800px;'):
                        ui.label(get_text('add_new_provider')).classes('text-h6')
                        with ui.column().classes('w-full'):
                            name_input = ui.input(get_text('name')).props('filled').classes('w-full')
                            endpoint_input = ui.input(get_text('api_endpoint')).props('filled').classes('w-full')
                            key_input = ui.input(get_text('api_key'), password=True).props('filled').classes('w-full')
                            model_input = ui.input(get_text('model')).props('filled').classes('w-full')
                            price_input = ui.number(get_text('price_per_million_tokens')).props('filled').classes('w-full')
                            type_select = ui.select(['per_token', 'per_call'], value='per_token', label=get_text('type')).props('filled').classes('w-full')
                            active_toggle = ui.switch(get_text('active'), value=True)

                        def handle_add():
                            url = endpoint_input.value.strip()
                            parsed = urlparse(url)
                            # If there's no path component, assume it's a base URL and complete it
                            if not parsed.path or parsed.path == '/':
                                final_endpoint = f"{url.rstrip('/')}/v1/chat/completions"
                                ui.notify(f"Endpoint auto-completed to: {final_endpoint}", color='info')
                            else:
                                final_endpoint = url

                            provider_data = schemas.ApiProviderCreate(
                                name=name_input.value,
                                api_endpoint=final_endpoint,
                                api_key=key_input.value,
                                model=model_input.value,
                                price_per_million_tokens=price_input.value,
                                type=type_select.value,
                                is_active=active_toggle.value
                            )
                            crud.create_provider(db, provider_data)
                            ui.notify(get_text('provider_added').format(name=name_input.value), color='positive')
                            refresh_providers_table()
                            add_dialog.close()

                        with ui.row():
                            ui.button(get_text('add'), on_click=handle_add, color='primary')
                            ui.button(get_text('cancel'), on_click=add_dialog.close)

                    # Import Models Dialog
                    with ui.dialog() as import_dialog, ui.card().style('width: 60vw; max-width: 800px;'):
                        ui.label(get_text('import_models_from_url')).classes('text-h6')
                        with ui.column().classes('w-full'):
                            base_url_input = ui.input(get_text('base_url'), value='https://xxxx').props('filled').classes('w-full')
                            api_key_input = ui.input(get_text('api_key'), password=True).props('filled').classes('w-full')
                            alias_input = ui.input(get_text('alias_optional'), placeholder='e.g., ollama').props('filled').classes('w-full')
                            default_type_select = ui.select(['per_token', 'per_call'], value='per_token', label=get_text('default_type')).props('filled').classes('w-full')
                            with ui.row().classes('w-full no-wrap'):
                                filter_mode_select = ui.select(['None', 'Include', 'Exclude'], value='None', label=get_text('filter_mode')).props('filled').classes('w-1/3')
                                filter_keyword_input = ui.input(get_text('model_name_filter')).props('filled').classes('flex-grow')
                        
                        with ui.element('div').classes('w-full relative h-6') as progress_container:
                            progress = ui.linear_progress(value=0, show_value=False).props('rounded size="25px" color="positive" striped').classes('w-full h-full')
                            progress_label = ui.label('0.0%').classes('absolute-full flex flex-center text-white font-medium')
                        progress_container.visible = False

                        async def handle_import():
                            progress_container.visible = True
                            progress.value = 0
                            progress_label.text = '0.0%'
                            
                            try:
                                api_url = "http://127.0.0.1:8001/api/import-models/"
                                payload = {
                                    "base_url": base_url_input.value,
                                    "api_key": api_key_input.value,
                                    "alias": alias_input.value,
                                    "default_type": default_type_select.value,
                                    "filter_mode": filter_mode_select.value,
                                    "filter_keyword": filter_keyword_input.value
                                }
                                
                                import httpx
                                async with httpx.AsyncClient() as client:
                                    async with client.stream("POST", api_url, json=payload, timeout=None) as response:
                                        if response.status_code != 200:
                                            error_detail = (await response.aread()).decode()
                                            ui.notify(f"Error: {error_detail}", color='negative')
                                            progress_container.visible = False
                                            return

                                        total = 0
                                        imported_count = 0
                                        async for line in response.aiter_lines():
                                            if line.startswith('data:'):
                                                data = line[len('data:'):].strip()
                                                if data.startswith('TOTAL='):
                                                    total = int(data.split('=')[1])
                                                    ui.notify(f'Found {total} models. Starting import...')
                                                elif data.startswith('PROGRESS='):
                                                    imported_count = int(data.split('=')[1])
                                                    if total > 0:
                                                        progress_value = imported_count / total
                                                        progress.value = progress_value
                                                        progress_label.text = f'{progress_value * 100:.1f}%'
                                                elif data.startswith('DONE='):
                                                    final_message = data.split('=', 1)[1]
                                                    ui.notify(final_message, color='positive')
                                                    refresh_providers_table()
                                                    await asyncio.sleep(1)
                                                    import_dialog.close()
                                                elif data.startswith('ERROR='):
                                                    error_message = data.split('=', 1)[1]
                                                    ui.notify(error_message, color='negative')

                            except httpx.ConnectError as e:
                                ui.notify(f"Connection Error: Could not connect to the backend API at {api_url}. Is the server running?", color='negative')
                            except Exception as e:
                                ui.notify(f"An unexpected error occurred: {e}", color='negative')
                            finally:
                                progress_container.visible = False
                                progress.value = 0
                                progress_label.text = '0.0%'


                        with ui.row():
                            ui.button(get_text('import'), on_click=handle_import, color='primary')
                            ui.button(get_text('cancel'), on_click=import_dialog.close)

                    def open_quick_remove_dialog():
                        with ui.dialog() as dialog, ui.card().style('width: 60vw; max-width: 800px;'):
                            ui.label(get_text('quick_remove_by_api_key')).classes('text-h6')

                            def get_keys():
                                return [k[0] for k in crud.get_all_unique_keys(db)]

                            def handle_quick_remove(key_select):
                                key = key_select.value
                                if not key:
                                    ui.notify('An API Key must be selected.', color='negative')
                                    return
                                
                                deleted_count = crud.delete_providers_by_key(db, key)
                                ui.notify(f'Removed {deleted_count} providers with the selected key.', color='positive')
                                refresh_providers_table()
                                dialog.close()

                            qr_key_select = ui.select(options=get_keys(), label=get_text('api_key')).props('filled').classes('w-full')

                            with ui.row():
                                ui.button(get_text('remove'), on_click=lambda: handle_quick_remove(qr_key_select), color='negative')
                                ui.button(get_text('cancel'), on_click=dialog.close)
                        dialog.open()

                    columns = [
                        {'name': 'id', 'label': get_text('id'), 'field': 'id', 'sortable': True},
                        {'name': 'name', 'label': get_text('name'), 'field': 'name', 'sortable': True, 'align': 'left'},
                        {'name': 'model', 'label': get_text('model'), 'field': 'model', 'sortable': True},
                        {'name': 'price_per_million_tokens', 'label': get_text('price_dollar_per_1m'), 'field': 'price_per_million_tokens', 'sortable': True},
                        {'name': 'is_active', 'label': get_text('active'), 'field': 'is_active', 'sortable': True},
                        {'name': 'actions', 'label': get_text('actions'), 'field': 'actions'},
                    ]
                    
                    with ui.row().classes('items-center gap-2'):
                        ui.button(get_text('add_provider'), on_click=add_dialog.open, color='primary')
                        ui.button(get_text('import_from_url'), on_click=import_dialog.open, color='primary')
                        ui.button(get_text('quick_remove'), on_click=open_quick_remove_dialog, color='negative')
                    
                    table = ui.table(columns=columns, rows=get_all_providers_as_dict(), row_key='id').classes('w-full mt-4')
                    
                    table.add_slot('body-cell-actions', '''
                        <q-td :props="props">
                            <q-btn @click="$parent.$emit('edit', props.row)" icon="edit" flat dense color="primary" />
                            <q-btn @click="$parent.$emit('delete', props.row)" icon="delete" flat dense color="negative" />
                        </q-td>
                    ''')

                    with ui.dialog() as edit_dialog, ui.card().style('width: 60vw; max-width: 800px;'):
                        ui.label(get_text('edit_provider')).classes('text-h6')
                        edit_id = ui.label()
                        with ui.column().classes('w-full'):
                            edit_name_input = ui.input(get_text('name')).props('filled').classes('w-full')
                            edit_endpoint_input = ui.input(get_text('api_endpoint')).props('filled').classes('w-full')
                            edit_key_input = ui.input(get_text('api_key'), password=True).props('filled').classes('w-full')
                            edit_model_input = ui.input(get_text('model')).props('filled').classes('w-full')
                            edit_price_input = ui.number(get_text('price_per_million_tokens')).props('filled').classes('w-full')
                            edit_type_select = ui.select(['per_token', 'per_call'], label=get_text('type')).props('filled').classes('w-full')
                            edit_active_toggle = ui.switch(get_text('active'))

                        def handle_edit():
                            url = edit_endpoint_input.value.strip()
                            parsed = urlparse(url)
                            # If there's no path component, assume it's a base URL and complete it
                            if not parsed.path or parsed.path == '/':
                                final_endpoint = f"{url.rstrip('/')}/v1/chat/completions"
                                ui.notify(f"Endpoint auto-completed to: {final_endpoint}", color='info')
                            else:
                                final_endpoint = url
                            
                            provider_data = {
                                "name": edit_name_input.value,
                                "api_endpoint": final_endpoint,
                                "model": edit_model_input.value,
                                "price_per_million_tokens": edit_price_input.value,
                                "type": edit_type_select.value,
                                "is_active": edit_active_toggle.value
                            }
                            if edit_key_input.value:
                                provider_data['api_key'] = edit_key_input.value

                            crud.update_provider(db, edit_id.text, provider_data)
                            ui.notify(get_text('provider_updated').format(name=edit_name_input.value), color='positive')
                            refresh_providers_table()
                            edit_dialog.close()

                        with ui.row():
                            ui.button(get_text('save'), on_click=handle_edit, color='primary')
                            ui.button(get_text('cancel'), on_click=edit_dialog.close)

                    def open_edit_dialog(e):
                        row = e.args
                        edit_id.text = row['id']
                        edit_name_input.value = row['name']
                        edit_endpoint_input.value = row['api_endpoint']
                        edit_key_input.value = ''
                        edit_key_input.props('placeholder="Enter new key to change"')
                        edit_model_input.value = row['model']
                        edit_price_input.value = row['price_per_million_tokens']
                        edit_type_select.value = row['type']
                        edit_active_toggle.value = row['is_active']
                        edit_dialog.open()

                    async def open_delete_dialog(e):
                        row = e.args
                        with ui.dialog() as delete_dialog, ui.card().style('width: 60vw; max-width: 800px;'):
                            ui.label(get_text('delete_provider_confirm').format(name=row['name']))
                            with ui.row():
                                def handle_delete():
                                    crud.delete_provider(db, row['id'])
                                    ui.notify(get_text('provider_deleted').format(name=row['name']), color='negative')
                                    refresh_providers_table()
                                    delete_dialog.close()
                                ui.button(get_text('delete'), on_click=handle_delete, color='negative')
                                ui.button(get_text('cancel'), on_click=delete_dialog.close)
                        await delete_dialog

                    table.on('edit', open_edit_dialog)
                    table.on('delete', open_delete_dialog)

                with ui.tab_panel(groups_tab) as panel:

                    def get_groups_with_providers():
                        db.expire_all()
                        groups = crud.get_groups(db)
                        providers = crud.get_providers(db)
                        group_data = []
                        for group in groups:
                            associations = db.query(models.provider_group_association).filter_by(group_id=group.id).all()
                            group_providers = {assoc.provider_id: {"priority": assoc.priority} for assoc in associations}
                            group_data.append({'id': group.id, 'name': group.name, 'providers': group_providers})
                        return group_data, providers

                    def build_groups_view():
                        groups_container.clear()
                        group_data, providers = get_groups_with_providers()

                        if not group_data:
                            with groups_container:
                                ui.label(get_text('no_groups_created'))
                            return

                        def get_priority_style(p_value):
                            if not isinstance(p_value, (int, float)): p_value = 1
                            p_value = max(1, min(10, p_value))
                            indicator_width = (11 - p_value) * 10
                            return f'width: {indicator_width}%;'

                        async def handle_save_group(group_data):
                            initial_providers = group_data.get('providers', {})
                            current_controls = group_data.get('controls', {})
                            changes_made = False
                            for pid, ctrls in current_controls.items():
                                if ctrls['switch'].value:
                                    new_priority = int(ctrls['priority'].value)
                                    if pid not in initial_providers or initial_providers[pid].get('priority') != new_priority:
                                        crud.add_provider_to_group(db, provider_id=pid, group_id=group_data['id'], priority=new_priority)
                                        changes_made = True
                                else:
                                    if pid in initial_providers:
                                        crud.remove_provider_from_group(db, provider_id=pid, group_id=group_data['id'])
                                        changes_made = True
                            if changes_made:
                                ui.notify(get_text('group_updated').format(name=group_data['name']), color='positive')
                                await refresh_groups_view()
                            else:
                                ui.notify(get_text('no_changes_to_save'))
                        
                        async def open_delete_group_dialog(group_id, group_name):
                            with ui.dialog() as delete_dialog, ui.card():
                                ui.label(get_text('delete_group_confirm').format(name=group_name))
                                with ui.row():
                                    async def handle_delete():
                                        crud.delete_group(db, group_id)
                                        ui.notify(get_text('group_deleted').format(name=group_name), color='negative')
                                        delete_dialog.close()
                                        await refresh_groups_view()
                                    ui.button(get_text('delete'), on_click=handle_delete, color='negative')
                                    ui.button(get_text('cancel'), on_click=delete_dialog.close)
                            await delete_dialog

                        with groups_container:
                            for group in group_data:
                                with ui.expansion(group['name'], icon='group').classes('w-full mb-2'):
                                    with ui.row().classes('w-full items-center'):
                                        ui.label(f"{get_text('group_id')}: {group['id']}").classes('text-caption')
                                        ui.space()
                                        ui.button(icon='delete', on_click=lambda g=group: open_delete_group_dialog(g['id'], g['name']), color='negative').props('flat dense')

                                    with ui.grid().classes('w-full grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2'):
                                        group['controls'] = {}
                                        for provider in providers:
                                            with ui.card().classes('p-2'):
                                                is_member = provider.id in group['providers']
                                                switch = ui.switch(provider.name, value=is_member).classes('w-full')
                                                ui.label(f"{get_text('model')}: {provider.model}").classes('text-xs ml-1')
                                                priority = group['providers'].get(provider.id, {}).get('priority', 1)
                                                with ui.element('div').classes('w-full'):
                                                    number_input = ui.number(get_text('priority'), value=priority, min=1, max=10, format='%.0f').props('outlined dense style="width: 100%;"').classes('bg-white')
                                                    with ui.element('div').classes('w-full h-1.5 bg-gray-200 rounded-full mt-1'):
                                                        indicator_bar = ui.element('div').classes('h-1.5 rounded-full transition-all duration-300').style('background-color: #2F6BFF')
                                                indicator_bar.style(get_priority_style(priority))
                                                number_input.on('update:model-value', lambda e, bar=indicator_bar: bar.style(get_priority_style(e.args)))
                                                group['controls'][provider.id] = {'switch': switch, 'priority': number_input}

                                    with ui.row().classes('w-full mt-2 justify-end'):
                                        ui.button(get_text('save_changes'), on_click=lambda g=group: handle_save_group(g)).props('color="primary"')

                    async def refresh_groups_view():
                        async with loading_animation():
                            build_groups_view()
                        ui.notify(get_text('groups_view_refreshed'), color='positive')

                    # --- Static UI Elements ---
                    panel.on('show', refresh_groups_view)
                    with ui.row().classes('w-full items-center'):
                        ui.label(get_text('provider_groups')).classes('text-h6')
                        ui.space()
                        ui.button(get_text('refresh_groups'), on_click=refresh_groups_view, icon='refresh', color='primary').props('flat')
                    
                    ui.label(get_text('groups_description')).classes('mb-4')

                    with ui.dialog() as add_group_dialog, ui.card().style('width: 60vw; max-width: 800px;'):
                        ui.label(get_text('create_new_group')).classes('text-h6')
                        group_name_input = ui.input(get_text('group_name')).props('filled').classes('w-full')
                        async def handle_add_group():
                            if not group_name_input.value:
                                ui.notify(get_text('group_name_empty_error'), color='negative')
                                return
                            if crud.get_group_by_name(db, group_name_input.value):
                                ui.notify(get_text('group_exists_error').format(name=group_name_input.value), color='negative')
                                return
                            crud.create_group(db, schemas.GroupCreate(name=group_name_input.value))
                            ui.notify(get_text('group_created').format(name=group_name_input.value), color='positive')
                            add_group_dialog.close()
                            await refresh_groups_view()
                        with ui.row():
                            ui.button(get_text('create'), on_click=handle_add_group, color='primary')
                            ui.button(get_text('cancel'), on_click=add_group_dialog.close)
                    
                    ui.button(get_text('create_group'), on_click=add_group_dialog.open, color='primary')

                    # --- Dynamic Content Area ---
                    groups_container = ui.column().classes('w-full mt-4')
                    build_groups_view()


                with ui.tab_panel(logs_tab):
                    def get_logs_with_provider_info():
                        logs = crud.get_call_logs(db)
                        log_data = []
                        for log in logs:
                            data = {key: getattr(log, key) for key in log.__table__.columns.keys()}
                            data['api_endpoint'] = log.provider.api_endpoint
                            data['model'] = log.provider.model
                            if data.get('request_timestamp'):
                                data['request_timestamp'] = data['request_timestamp'].strftime('%Y-%m-%d %H:%M:%S')
                            log_data.append(data)
                        return log_data

                    async def refresh_logs_table():
                        async with loading_animation():
                            logs_table.update_rows(get_logs_with_provider_info())
                        ui.notify(get_text('logs_refreshed'), color='positive')

                    with ui.row().classes('w-full items-center'):
                        ui.label(get_text('call_logs')).classes('text-h6')
                        ui.space()
                        ui.button(get_text('refresh_logs'), on_click=refresh_logs_table, icon='refresh', color='primary').props('flat')
                    log_columns = [
                        {'name': 'id', 'label': get_text('id'), 'field': 'id', 'sortable': True},
                        {'name': 'api_endpoint', 'label': get_text('api_endpoint'), 'field': 'api_endpoint', 'sortable': True},
                        {'name': 'model', 'label': get_text('model'), 'field': 'model', 'sortable': True},
                        {'name': 'request_timestamp', 'label': get_text('timestamp'), 'field': 'request_timestamp', 'sortable': True},
                        {'name': 'is_success', 'label': get_text('success'), 'field': 'is_success'},
                        {'name': 'status_code', 'label': get_text('status'), 'field': 'status_code'},
                        {'name': 'response_time_ms', 'label': get_text('response_time_ms'), 'field': 'response_time_ms', 'sortable': True},
                        {'name': 'prompt_tokens', 'label': get_text('prompt_tokens'), 'field': 'prompt_tokens', 'sortable': True},
                        {'name': 'completion_tokens', 'label': get_text('completion_tokens'), 'field': 'completion_tokens', 'sortable': True},
                        {'name': 'total_tokens', 'label': get_text('total_tokens'), 'field': 'total_tokens', 'sortable': True},
                        {'name': 'cost', 'label': get_text('cost'), 'field': 'cost', 'sortable': True},
                        {'name': 'error_message', 'label': get_text('error'), 'field': 'error_message'},
                        {'name': 'actions', 'label': get_text('actions'), 'field': 'actions'},
                    ]


                    import json

                    # Dialog to display the response body
                    with ui.dialog() as response_dialog, ui.card().style('min-width: 60vw; max-width: 80vw;'):
                        def copy_response_body():
                            # Escape backticks and backslashes for JS template literal
                            content_to_copy = response_content_area.content.replace('\\', '\\\\').replace('`', '\\`')
                            js_command = f"navigator.clipboard.writeText(`{content_to_copy}`)"
                            ui.run_javascript(js_command)
                            ui.notify(get_text('copied_to_clipboard'), color='positive')

                        with ui.row().classes('w-full no-wrap justify-between items-center'):
                            ui.label(get_text('response_body')).classes('text-h6')
                            with ui.button(icon='content_copy', on_click=copy_response_body).props('flat round dense'):
                                ui.tooltip(get_text('copy_tooltip'))

                        response_content_area = ui.code('').classes('w-full max-h-[60vh] overflow-auto bg-gray-900 text-white p-4 rounded-lg font-mono custom-scrollbar')
                        with ui.row().classes('w-full justify-end'):
                            ui.button(get_text('close'), on_click=response_dialog.close, color='primary')

                    def show_response_body(e):
                        row_data = e.args
                        body = row_data.get('response_body')
                        if body:
                            try:
                                # Try to parse and pretty-print JSON
                                parsed_json = json.loads(body)
                                formatted_body = json.dumps(parsed_json, indent=2, ensure_ascii=False)
                                response_content_area.content = formatted_body
                                response_content_area.language = 'json'
                            except (json.JSONDecodeError, TypeError):
                                # If it's not valid JSON, display as plain text
                                response_content_area.content = body
                                response_content_area.language = 'text'
                        else:
                            response_content_area.content = "No response body saved."
                            response_content_area.language = 'text'
                        
                        response_content_area.update()
                        response_dialog.open()

                    logs_table = ui.table(
                        columns=log_columns,
                        rows=get_logs_with_provider_info(),
                        row_key='id'
                    ).classes('w-full')
                    
                    logs_table.add_slot('body-cell-actions', f'''
                        <q-td :props="props">
                            <q-btn @click="$parent.$emit('view_log', props.row)" icon="visibility" flat dense color="primary">
                                <q-tooltip>{get_text('view')}</q-tooltip>
                            </q-btn>
                        </q-td>
                    ''')

                    logs_table.on('view_log', show_response_body)

                    logs_table.add_slot('body-cell-cost', '''
                        <q-td :props="props">
                            {{ props.row.cost !== null ? props.row.cost.toFixed(6) : 'N/A' }}
                        </q-td>
                    ''')

                with ui.tab_panel(errors_tab):
                    async def refresh_keywords_table_async():
                        async with loading_animation():
                            keywords_table.update_rows([{key: getattr(kw, key) for key in kw.__table__.columns.keys()} for kw in crud.get_error_keywords(db)])
                        ui.notify(get_text('keywords_refreshed'), color='positive')

                    def refresh_keywords_table():
                        keywords_table.update_rows([{key: getattr(kw, key) for key in kw.__table__.columns.keys()} for kw in crud.get_error_keywords(db)])

                    with ui.row().classes('w-full items-center'):
                        ui.label(get_text('failure_keywords')).classes('text-h6')
                        ui.space()
                        ui.button(get_text('refresh_keywords'), on_click=refresh_keywords_table_async, icon='refresh', color='primary').props('flat')
                    
                    ui.label(get_text('failure_keywords_description')).classes('mb-4')

                    with ui.dialog() as add_keyword_dialog, ui.card().style('width: 60vw; max-width: 800px;'):
                        ui.label(get_text('add_failure_keyword')).classes('text-h6')
                        with ui.column().classes('w-full'):
                            keyword_input = ui.input(get_text('keyword_case_insensitive')).props('filled').classes('w-full')
                            desc_input = ui.input(get_text('description')).props('filled').classes('w-full')
                        
                        def handle_add_keyword():
                            keyword_data = schemas.ErrorKeywordCreate(keyword=keyword_input.value, description=desc_input.value)
                            crud.create_error_keyword(db, keyword_data)
                            ui.notify(get_text('keyword_added').format(keyword=keyword_input.value), color='positive')
                            refresh_keywords_table()
                            add_keyword_dialog.close()

                        with ui.row():
                            ui.button(get_text('add'), on_click=handle_add_keyword, color='primary')
                            ui.button(get_text('cancel'), on_click=add_keyword_dialog.close)

                    keyword_columns = [
                        {'name': 'id', 'label': get_text('id'), 'field': 'id', 'sortable': True},
                        {'name': 'keyword', 'label': get_text('keyword'), 'field': 'keyword', 'sortable': True},
                        {'name': 'description', 'label': get_text('description'), 'field': 'description'},
                        {'name': 'is_active', 'label': get_text('active'), 'field': 'is_active'},
                        {'name': 'last_triggered', 'label': get_text('last_triggered'), 'field': 'last_triggered', 'sortable': True},
                        {'name': 'actions', 'label': get_text('actions'), 'field': 'actions'},
                    ]

                    ui.button(get_text('add_keyword'), on_click=add_keyword_dialog.open, color='primary').classes('mb-4')
                    keywords_table = ui.table(columns=keyword_columns, rows=[{key: getattr(kw, key) for key in kw.__table__.columns.keys()} for kw in crud.get_error_keywords(db)], row_key='id').classes('w-full')
                    
                    keywords_table.add_slot('body-cell-actions', '''
                        <q-td :props="props">
                            <q-btn @click="$parent.$emit('delete_keyword', props.row)" icon="delete" flat dense color="negative" />
                        </q-td>
                    ''')

                    async def open_delete_keyword_dialog(e):
                        row = e.args
                        with ui.dialog() as delete_dialog, ui.card().style('width: 60vw; max-width: 800px;'):
                            ui.label(get_text('delete_keyword_confirm').format(keyword=row['keyword']))
                            with ui.row():
                                def handle_delete():
                                    crud.delete_error_keyword(db, row['id'])
                                    ui.notify(get_text('keyword_deleted').format(keyword=row['keyword']), color='negative')
                                    refresh_keywords_table()
                                    delete_dialog.close()
                                ui.button(get_text('delete'), on_click=handle_delete, color='negative')
                                ui.button(get_text('cancel'), on_click=delete_dialog.close)
                        await delete_dialog

                    keywords_table.on('delete_keyword', open_delete_keyword_dialog)
                with ui.tab_panel(api_keys_tab):
                    def get_all_api_keys():
                        db.expire_all()
                        keys = crud.get_api_keys(db)
                        return [
                            {
                                "id": key.id,
                                "key_display": f"{key.key[:5]}...{key.key[-4:]}",
                                "key": key.key,
                                "is_active": key.is_active,
                                "created_at": key.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                                "last_used_at": key.last_used_at.strftime("%Y-%m-%d %H:%M:%S") if key.last_used_at else get_text('never'),
                                "groups": ", ".join([g.name for g in key.groups]),
                                "group_ids": [g.id for g in key.groups]
                            } for key in keys
                        ]

                    columns = [
                        {'name': 'key_display', 'label': get_text('key'), 'field': 'key_display', 'align': 'left'},
                        {'name': 'is_active', 'label': get_text('active'), 'field': 'is_active', 'sortable': True},
                        {'name': 'groups', 'label': get_text('groups'), 'field': 'groups', 'align': 'left'},
                        {'name': 'created_at', 'label': get_text('created_at'), 'field': 'created_at', 'sortable': True},
                        {'name': 'last_used_at', 'label': get_text('last_used'), 'field': 'last_used_at', 'sortable': True},
                        {'name': 'actions', 'label': get_text('actions'), 'field': 'actions'},
                    ]
                    def refresh_keys_table():
                        keys_table.update_rows(get_all_api_keys())

                    async def refresh_keys_table_async():
                        async with loading_animation():
                            refresh_keys_table()
                        ui.notify(get_text('api_keys_refreshed'), color='positive')

                    with ui.row().classes('w-full items-center mb-4'):
                        ui.label(get_text('api_keys')).classes('text-h6')
                        ui.space()
                        ui.button(get_text('refresh_api_keys'), on_click=refresh_keys_table_async, icon='refresh', color='primary').props('flat')

                    # This dialog is for showing the newly generated key
                    with ui.dialog() as show_key_dialog, ui.card().style('min-width: 400px;'):
                        ui.label(get_text('api_key_generated_successfully')).classes('text-h6')
                        ui.label(get_text('copy_key_instruction')).classes('text-sm text-gray-500')
                        
                        def copy_key():
                            ui.run_javascript(f"navigator.clipboard.writeText('{key_display_label.value}')")
                            ui.notify(get_text('copied_to_clipboard'), color='positive')

                        with ui.row().classes('w-full no-wrap items-center'):
                            key_display_label = ui.input(label=get_text('your_new_api_key')).props('readonly filled').classes('flex-grow')
                            ui.button(icon='content_copy', on_click=copy_key).props('flat dense')

                        with ui.row().classes('w-full justify-end mt-4'):
                            ui.button(get_text('close'), on_click=show_key_dialog.close, color='primary')

                    # This dialog is for creating a new key
                    with ui.dialog() as add_key_dialog, ui.card().style('width: 60vw; max-width: 800px;').classes('pb-12'):
                        ui.label(get_text('create_new_api_key')).classes('text-h6')
                        with ui.column().classes('w-full'):
                            async def refresh_group_options():
                                async with loading_animation():
                                    db.expire_all() # Ensure fresh data from DB
                                    all_group_names = [g.name for g in crud.get_groups(db)]
                                    group_select.options = all_group_names
                                    group_select.update()
                                ui.notify(get_text('group_list_refreshed'), color='info')

                            with ui.row().classes('w-full no-wrap items-center'):
                                all_group_names = [g.name for g in crud.get_groups(db)]
                                group_select = ui.select(all_group_names, multiple=True, label=get_text('assign_to_groups')).props('filled').classes('flex-grow')
                                ui.button(icon='refresh', on_click=refresh_group_options).props('flat dense color=primary')

                        def handle_add_key():
                            if not group_select.value:
                                ui.notify(get_text('assign_to_at_least_one_group_error'), color='negative')
                                return
                            
                            group_ids = [g.id for g in crud.get_groups(db) if g.name in group_select.value]
                            key_data = schemas.APIKeyCreate(group_ids=group_ids)
                            new_key = crud.create_api_key(db, key_data)
                            
                            key_display_label.value = new_key.key
                            show_key_dialog.open()

                            ui.notify(get_text('api_key_created'), color='positive')
                            refresh_keys_table()
                            add_key_dialog.close()

                        with ui.row():
                            ui.button(get_text('create'), on_click=handle_add_key, color='primary')
                            ui.button(get_text('cancel'), on_click=add_key_dialog.close)
                    
                    ui.button(get_text('create_api_key'), on_click=add_key_dialog.open, color='primary').classes('mb-4')
                    
                    keys_table = ui.table(columns=columns, rows=[], row_key='id').classes('w-full')
                    keys_table.add_slot('body-cell-key_display', '''
                        <q-td :props="props">
                            <div class="row items-center no-wrap">
                                <span>{{ props.row.key_display }}</span>
                                <q-btn @click="$parent.$emit('copy-key', props.row.key)" icon="content_copy" flat dense color="primary" class="cursor-pointer" />
                            </div>
                        </q-td>
                    ''')
                    keys_table.add_slot('body-cell-actions', '''
                        <q-td :props="props">
                            <q-btn @click="$parent.$emit('edit_key', props.row)" icon="edit" flat dense color="primary" />
                            <q-btn @click="$parent.$emit('toggle_key', props.row)" :icon="props.row.is_active ? 'toggle_on' : 'toggle_off'" flat dense :color="props.row.is_active ? 'positive' : 'grey'" />
                            <q-btn @click="$parent.$emit('delete_key', props.row)" icon="delete" flat dense color="negative" />
                        </q-td>
                    ''')

                    with ui.dialog() as edit_key_dialog, ui.card().style('width: 60vw; max-width: 800px;'):
                        ui.label(get_text('edit_api_key')).classes('text-h6')
                        edit_key_id = ui.label()
                        with ui.column().classes('w-full'):
                            async def refresh_edit_group_options():
                                async with loading_animation():
                                    db.expire_all()
                                    all_group_names = [g.name for g in crud.get_groups(db)]
                                    edit_group_select.options = all_group_names
                                    edit_group_select.update()
                                ui.notify(get_text('group_list_refreshed'), color='info')

                            with ui.row().classes('w-full no-wrap items-center'):
                                all_groups_edit = [g.name for g in crud.get_groups(db)]
                                edit_group_select = ui.select(all_groups_edit, multiple=True, label=get_text('assigned_groups')).props('filled').classes('flex-grow')
                                ui.button(icon='refresh', on_click=refresh_edit_group_options).props('flat dense color=primary')

                        def handle_edit_key():
                            group_ids = [g.id for g in crud.get_groups(db) if g.name in edit_group_select.value]
                            update_data = schemas.APIKeyUpdate(group_ids=group_ids)
                            crud.update_api_key(db, int(edit_key_id.text), update_data)
                            ui.notify(get_text('api_key_updated'), color='positive')
                            refresh_keys_table()
                            edit_key_dialog.close()

                        with ui.row():
                            ui.button(get_text('save'), on_click=handle_edit_key, color='primary')
                            ui.button(get_text('cancel'), on_click=edit_key_dialog.close)

                    def open_edit_key_dialog(e):
                        row = e.args
                        edit_key_id.text = str(row['id'])
                        group_names = [g.name for g in crud.get_groups(db) if g.id in row['group_ids']]
                        edit_group_select.value = group_names
                        edit_key_dialog.open()

                    def handle_toggle_key(e):
                        row = e.args
                        update_data = schemas.APIKeyUpdate(is_active=not row['is_active'])
                        crud.update_api_key(db, row['id'], update_data)
                        ui.notify(get_text('api_key_status_changed'), color='positive')
                        refresh_keys_table()

                    async def open_delete_key_dialog(e):
                        row = e.args
                        with ui.dialog() as delete_dialog, ui.card():
                            ui.label(get_text('delete_api_key_confirm').format(key_display=row['key_display']))
                            with ui.row():
                                def perform_delete():
                                    crud.delete_api_key(db, row['id'])
                                    ui.notify(get_text('api_key_deleted'), color='negative')
                                    refresh_keys_table()
                                    delete_dialog.close()
                                ui.button(get_text('delete'), on_click=perform_delete, color='negative')
                                ui.button(get_text('cancel'), on_click=delete_dialog.close)
                        await delete_dialog

                    def handle_copy_key(e):
                        key_to_copy = e.args
                        ui.run_javascript(f"navigator.clipboard.writeText('{key_to_copy}')")
                        ui.notify(get_text('copied_to_clipboard'), color='positive')

                    keys_table.on('copy-key', handle_copy_key)
                    keys_table.on('edit_key', open_edit_key_dialog)
                    keys_table.on('toggle_key', handle_toggle_key)
                    keys_table.on('delete_key', open_delete_key_dialog)

                    refresh_keys_table()

                with ui.tab_panel(settings_tab):
                    with ui.row().classes('w-full items-center'):
                        ui.label(get_text('settings')).classes('text-h6')
                    
                    with ui.card().classes('w-full mt-4'):
                        ui.label(get_text('failover_settings')).classes('text-lg font-medium')
                        ui.label(get_text('failover_description')).classes('text-sm text-gray-500 mb-4')
                        
                        # Fetch current settings or use defaults
                        failover_count_setting = crud.get_setting(db, 'failover_threshold_count')
                        failover_period_setting = crud.get_setting(db, 'failover_threshold_period_minutes')
                        
                        failover_count_input = ui.number(
                            label=get_text('failure_count_threshold'),
                            value=int(failover_count_setting.value) if failover_count_setting else 2,
                            min=1
                        ).props('filled')
                        
                        failover_period_input = ui.number(
                            label=get_text('failure_period_minutes'),
                            value=int(failover_period_setting.value) if failover_period_setting else 5,
                            min=1
                        ).props('filled')

                        def save_settings():
                            try:
                                crud.update_setting(db, 'failover_threshold_count', str(int(failover_count_input.value)))
                                crud.update_setting(db, 'failover_threshold_period_minutes', str(int(failover_period_input.value)))
                                ui.notify(get_text('settings_saved'), color='positive')
                            except Exception as e:
                                ui.notify(f"Error saving settings: {e}", color='negative')

                        ui.button(get_text('save'), on_click=save_settings, color='primary').classes('mt-4')

        else:
            # If the user is not authenticated, show the new login page.
            async def try_login():
                """Try to log the user in and display errors on failure."""
                username.error = None
                password.error = None

                if not username.value or not password.value:
                    if not username.value:
                        username.error = 'Please enter a username'
                    if not password.value:
                        password.error = 'Please enter a password'
                    ui.notify('Please fill in all fields', color='warning', position='top')
                    return

                if username.value == ADMIN_USERNAME and password.value == ADMIN_PASSWORD:
                    app.storage.user['authenticated'] = True
                    ui.notify('Login successful!', color='positive', position='top')
                    await asyncio.sleep(1)
                    ui.navigate.reload()
                else:
                    username.error = 'Incorrect username or password'
                    password.error = 'Incorrect username or password'
                    password.value = ''
                    ui.notify('Login failed, please check your username and password', color='negative', position='top')

            # Add custom fonts and styling to the page head
            ui.add_head_html('''
                <style>
                    @import url('/css/css2?family=Noto+Sans:wght@300;400;500;700&display=swap');
                    body { font-family: 'Noto Sans', sans-serif; }
                    .nicegui-content { padding: 0 !important; }
                    .login-bg {
                        position: absolute;
                        top: 0; left: 0; width: 100%; height: 100%;
                        overflow: hidden;
                        z-index: 0;
                    }
                    .login-bg canvas {
                        width: 100% !important;
                        height: 100% !important;
                    }
                    .brand-content { z-index: 1; }
                </style>
            ''')

            # Set page background
            ui.query('body').style(f'background-color: #F3F4F6;')

            with ui.element('div').classes('flex w-screen h-screen overflow-y-hidden relative'):
                # Left Panel (Login Form) - 40% width
                with ui.element('div').classes('w-full lg:w-[40%] h-full bg-[#111827] flex flex-col justify-center items-center p-8'):
                    with ui.card().classes('w-full max-w-md p-8 rounded-lg shadow-xl bg-transparent text-white'):
                        # Brand Logo and Title
                        with ui.element('div').classes('flex flex-col items-center text-center mb-8 w-full brand-content'):
                            ui.image('/images/favicon.png').classes('w-16 h-16')
                            ui.label(get_text('niceapi_title')).classes('text-5xl font-bold mt-4')
                            ui.label(get_text('niceapi_subtitle')).classes('text-xl font-light text-gray-300 mt-2')

                        # Username Input
                        username = ui.input(placeholder=get_text('username')) \
                            .props('outlined dense dark color="white" bg-color="rgba(255, 255, 255, 0.1)"') \
                            .classes('w-full text-lg')
                        with username.add_slot('prepend'):
                            ui.icon('o_person', color='white').classes('flex-center')
                        username.on('update:model-value', lambda: setattr(username, 'error', None))

                        # Password Input
                        password = ui.input(placeholder=get_text('password'), password=True) \
                            .props('outlined dense dark color="white" bg-color="rgba(255, 255, 255, 0.1)"') \
                            .classes('w-full mt-4 text-lg')
                        with password.add_slot('prepend'):
                            ui.icon('o_lock', color='white').classes('flex-center')
                        password.on('update:model-value', lambda: setattr(password, 'error', None))

                        # Login Button
                        ui.button(get_text('login'), on_click=try_login).props('color="primary" text-color="white" size="lg"').classes('w-full mt-8 py-3 text-lg font-bold')
                        
                        # Footer
                        with ui.row().classes('w-full justify-center mt-12'):
                            ui.label(get_text('copyright')).classes('text-xs text-gray-400')
                
                # Right Panel (Image) - 60% width, hidden on small screens
                with ui.element('div').classes('w-full lg:w-[60%] h-full lg:flex'):
                    ui.image('/images/bg.png').classes('w-full h-full object-cover')
            
            # JavaScript for the animated background
            ui.add_body_html(f'''
                <script src="/js/three.min.js"></script>
                <script>
                    document.addEventListener('DOMContentLoaded', () => {{
                        const container = document.querySelector('.login-bg');
                        if (!container) return;

                        const scene = new THREE.Scene();
                        const camera = new THREE.PerspectiveCamera(75, container.offsetWidth / container.offsetHeight, 0.1, 1000);
                        const renderer = new THREE.WebGLRenderer({{ alpha: true, antialias: true }});
                        renderer.setSize(container.offsetWidth, container.offsetHeight);
                        container.appendChild(renderer.domElement);

                        const particles = [];
                        const particleCount = 150;

                        for (let i = 0; i < particleCount; i++) {{
                            const geometry = new THREE.SphereGeometry(Math.random() * 0.03, 8, 8);
                            const material = new THREE.MeshBasicMaterial({{ color: 0xFFFFFF, transparent: true, opacity: Math.random() * 0.5 + 0.2 }});
                            const particle = new THREE.Mesh(geometry, material);
                            
                            particle.position.x = (Math.random() - 0.5) * 10;
                            particle.position.y = (Math.random() - 0.5) * 10;
                            particle.position.z = (Math.random() - 0.5) * 10;
                            
                            particle.velocity = new THREE.Vector3(
                                (Math.random() - 0.5) * 0.005,
                                (Math.random() - 0.5) * 0.005,
                                (Math.random() - 0.5) * 0.005
                            );
                            
                            particles.push(particle);
                            scene.add(particle);
                        }}
                        
                        camera.position.z = 5;

                        function animate() {{
                            requestAnimationFrame(animate);

                            particles.forEach(p => {{
                                p.position.add(p.velocity);

                                if (p.position.x < -5 || p.position.x > 5) p.velocity.x = -p.velocity.x;
                                if (p.position.y < -5 || p.position.y > 5) p.velocity.y = -p.velocity.y;
                                if (p.position.z < -5 || p.position.z > 5) p.velocity.z = -p.velocity.z;
                            }});

                            renderer.render(scene, camera);
                        }}

                        animate();

                        window.addEventListener('resize', () => {{
                            camera.aspect = container.offsetWidth / container.offsetHeight;
                            camera.updateProjectionMatrix();
                            renderer.setSize(container.offsetWidth, container.offsetHeight);
                        }});
                    }});
                </script>
            ''')
    
    # The db session is now managed by FastAPI's dependency injection,
    # so the app.on_shutdown hook is no longer needed.
    # app.on_shutdown(db.close)