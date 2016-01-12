from __future__ import print_function

from airflow import DAG
import airflow
from datetime import datetime, timedelta
from airflow.operators import BashOperator
from airflow.operators import ShortCircuitOperator
from airflow.operators.docker_operator import DockerOperator

'''
This sample "listen to directory". move the new file and print it, using docker-containers.
The following operators are being used: DockerOperator, BashOperator & ShortCircuitOperator.
'''

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime.now(),
    'email': ['airflow@airflow.com'],
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
        'docker_sample_copy_data', default_args=default_args, schedule_interval=timedelta(minutes=10))

# ==========================================================
ls_templated_cmd = """   
    sleep 10
    find {{params.source_location}} -type f  -printf "%f\n" | head -1      	
"""

t_view = BashOperator(
        task_id='view_file',
        bash_command=ls_templated_cmd,
        xcom_push=True,
        params={'source_location': '/your/input_dir/path'},
        dag=dag)


# =========================================================


def is_data_available(*args, **kwargs):
    ti = kwargs['ti']
    data = ti.xcom_pull(key=None, task_ids='view_file')
    return not data == ''


t_is_data_available = ShortCircuitOperator(
        task_id='check_if_data_available',
        provide_context=True,
        python_callable=is_data_available,
        dag=dag)

# ==========================================================	

mv_templated_cmd = """   
    "sleep 30"
    "mv {{params.source_location}}/{{ ti.xcom_pull('view_file') }} {{params.target_location}}"
    "echo '{{params.target_location}}/{{ ti.xcom_pull('view_file') }}'"
"""

t_move = DockerOperator(
        api_version='1.19',
        docker_url='tcp://localhost:2375',  # replace it with swarm/docker endpoint
        image='centos:latest',
        network_mode='bridge',
        volumes=['/your/host/input_dir/path:/your/input_dir/path',
                 '/your/host/output_dir/path:/your/output_dir/path'],
        command='./entrypoint.sh',
        task_id='move_data',
        xcom_push=True,
        params={'source_location': '/your/input_dir/path',
                'target_location': '/your/output_dir/path'},
        dag=dag)

# ==========================================================	


print_templated_cmd = """   
    cat {{ ti.xcom_pull('move_data') }}    
"""

t_print = DockerOperator(
        api_version='1.19',
        docker_url='tcp://localhost:2375',
        image='centos:latest',
        volumes=['/your/host/output_dir/path:/your/output_dir/path'],
        command=print_templated_cmd,
        task_id='print',
        dag=dag)

# =========================================================

t_view.set_downstream(t_is_data_available)
t_is_data_available.set_downstream(t_move)
t_move.set_downstream(t_print)
