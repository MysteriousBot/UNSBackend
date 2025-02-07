from django.shortcuts import render
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.db.models import Q, Sum
from django.db.models.functions import TruncDate
from .models import Staff, Job, JobAssignedStaff, Client, Task, Timesheet
from datetime import datetime, timedelta
from django.utils import timezone

# Create your views here.

@api_view(['POST'])
@permission_classes([AllowAny])
def check_staff_email(request):
    email = request.data.get('email')
    try:
        staff = Staff.objects.get(email=email)
        return Response({
            'exists': True,
            'staff_uuid': staff.uuid
        })
    except Staff.DoesNotExist:
        return Response({
            'exists': False
        })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_jobs(request, staff_uuid):
    try:
        print(f"Fetching jobs for staff_uuid: {staff_uuid}")
        
        # Get all job IDs assigned to the staff member
        job_assignments = JobAssignedStaff.objects.filter(staff_uuid=staff_uuid)
        print(f"Found {job_assignments.count()} job assignments")
        
        job_ids = job_assignments.values_list('job_id', flat=True)
        print(f"Job IDs: {list(job_ids)}")

        # Get all jobs with their related client data
        jobs = Job.objects.filter(id__in=job_ids).select_related('client').order_by('due_date').values(
            'id',
            'job_id',
            'name',
            'client_uuid',
            'state',
            'due_date'
        )
        print(f"Found {jobs.count()} jobs")

        # Get all client data in one query
        client_uuids = [job['client_uuid'] for job in jobs]
        clients = {
            client.uuid: client.name 
            for client in Client.objects.filter(uuid__in=client_uuids)
        }

        # Transform the data to match the frontend expectations
        transformed_jobs = []
        for job in jobs:
            transformed_jobs.append({
                'id': job['id'],
                'job_number': job['job_id'],
                'name': job['name'],
                'client_name': clients.get(job['client_uuid'], 'Unknown Client'),  # Get client name from dict
                'status': job['state'],
                'due_date': job['due_date']
            })

        return Response(transformed_jobs)
    except Exception as e:
        print(f"Error in my_jobs view: {str(e)}")
        return Response(
            {'error': str(e)}, 
            status=500
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def job_detail(request, job_id):
    try:
        # Get job details
        job = Job.objects.get(job_id=job_id)
        
        # Get tasks for this job with just the fields we need
        tasks = Task.objects.filter(job_id=job.id).values(
            'id',
            'name',
            'completed'  # Using the actual field name from the model
        )

        # Format response
        response_data = {
            'job_number': job.job_id,
            'name': job.name,
            'tasks': [
                {
                    'id': task['id'],
                    'name': task['name'],
                    'complete': task['completed']  # Using the actual field name
                }
                for task in tasks
            ]
        }

        return Response(response_data)
    except Job.DoesNotExist:
        return Response({'error': 'Job not found'}, status=404)
    except Exception as e:
        print(f"Error in job_detail view: {str(e)}")
        return Response({'error': str(e)}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def client_list(request):
    try:
        clients = Client.objects.all().values(
            'uuid',
            'name',
            'is_archived',  # Instead of status
            'phone',
            'address',  # This is the default address
            'city',
            'region',
            'country',
            'post_code',
            'email',
            'website',
            'type_name',
            'account_manager_name',
            'job_manager_name'
        ).order_by('name')
        
        # Transform the data to match the frontend expectations
        transformed_clients = []
        for client in clients:
            # Format the full address
            address_parts = [
                client['address'],
                client['city'],
                client['region'],
                client['post_code'],
                client['country']
            ]
            full_address = ', '.join(filter(None, address_parts))

            transformed_clients.append({
                'uuid': client['uuid'],
                'name': client['name'],
                'status': 'Archived' if client['is_archived'] else 'Active',
                'phone': client['phone'],
                'address': full_address,
                'email': client['email'],
                'website': client['website'],
                'type': client['type_name'],
                'account_manager': client['account_manager_name'],
                'job_manager': client['job_manager_name']
            })
        
        return Response(transformed_clients)
    except Exception as e:
        print(f"Error in client_list view: {str(e)}")
        return Response({'error': str(e)}, status=500)

@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def toggle_client_favorite(request, uuid):
    try:
        client = Client.objects.get(uuid=uuid)
        client.is_archived = not client.is_archived  # Using is_archived instead of favorite
        client.save()
        return Response({'status': 'success'})
    except Client.DoesNotExist:
        return Response({'error': 'Client not found'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def staff_weekly_hours(request, staff_uuid, week_start=None):
    try:
        # If no week_start provided, default to current week's Monday
        if not week_start:
            today = timezone.now().date()
            week_start = today - timedelta(days=today.weekday())
        else:
            # Parse the date and make it timezone aware
            week_start = datetime.strptime(week_start, '%Y-%m-%d').date()
        
        week_end = week_start + timedelta(days=6)

        # Make the datetime range timezone aware
        week_start_dt = timezone.make_aware(datetime.combine(week_start, datetime.min.time()))
        week_end_dt = timezone.make_aware(datetime.combine(week_end, datetime.max.time()))

        # Get all timesheet entries for the week
        timesheet_entries = Timesheet.objects.filter(
            staff_uuid=staff_uuid,
            entry_date__range=[week_start_dt, week_end_dt]
        )

        # Group by job and day
        job_hours = {}
        daily_hours = [0] * 7

        for entry in timesheet_entries:
            day_index = (entry.entry_date.date() - week_start).days
            hours = entry.minutes / 60

            # Add to daily totals
            daily_hours[day_index] = daily_hours[day_index] + hours

            # Add to job totals
            if entry.job_id not in job_hours:
                job_hours[entry.job_id] = {
                    'job_id': entry.job_id,
                    'name': entry.job_name,
                    'client_name': '',  # You might want to add this from your Job model
                    'daily_hours': [{'date': (week_start + timedelta(days=i)).strftime('%Y-%m-%d'), 'hours': 0} for i in range(7)]
                }
            
            job_hours[entry.job_id]['daily_hours'][day_index]['hours'] += hours

        # Format daily summary
        week_data = []
        for i in range(7):
            current_date = week_start + timedelta(days=i)
            week_data.append({
                'date': current_date.strftime('%Y-%m-%d'),
                'day': current_date.strftime('%a'),
                'hours': daily_hours[i]
            })

        return Response({
            'week_start': week_start.strftime('%Y-%m-%d'),
            'week_end': week_end.strftime('%Y-%m-%d'),
            'daily_hours': week_data,
            'job_hours': job_hours
        })

    except Exception as e:
        print(f"Error in staff_weekly_hours view: {str(e)}")
        return Response({'error': str(e)}, status=500)
