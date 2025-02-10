from django.shortcuts import render
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.db.models import Q, Sum
from django.db.models.functions import TruncDate
from .models import Staff, Job, JobAssignedStaff, Client, Task, Timesheet, Contact, TimeEntry
from datetime import datetime, timedelta
from django.utils import timezone
import uuid

# Create your views here.

@api_view(['POST'])
@permission_classes([AllowAny])
def check_staff_email(request):
    """
    Check if an email exists in Staff table and return the UUID if found.
    This endpoint is publicly accessible to support registration.
    """
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
        # First get the job to get its internal ID
        job = Job.objects.get(job_id=job_id)
        
        # Get all tasks for this job using the internal ID
        tasks = Task.objects.filter(job_id=job.id).values(
            'uuid',
            'name',
            'estimated_minutes',
            'completed'
        )

        # Get actual minutes from timesheet entries for each task
        for task in tasks:
            actual_minutes = Timesheet.objects.filter(
                task_uuid=task['uuid']
            ).aggregate(
                total_minutes=Sum('minutes')
            )['total_minutes'] or 0
            
            task['actual_minutes'] = actual_minutes
            task['remaining_minutes'] = task['estimated_minutes'] - actual_minutes if task['estimated_minutes'] else 0
            task['status'] = 'Incomplete'  # You can add more status logic here

        return Response({
            'job_id': job.job_id,
            'job_name': job.name,  # Include the job name in the response
            'tasks': tasks
        })

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

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def staff_weekly_hours(request, staff_uuid, week_start=None):
    if request.method == 'GET':
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

            # Get all timesheet entries and tasks for the week
            timesheet_entries = Timesheet.objects.filter(
                staff_uuid=staff_uuid,
                entry_date__range=[week_start_dt, week_end_dt]
            )

            # Get all tasks with their billable status
            tasks = {
                task.uuid: task.billable
                for task in Task.objects.filter(
                    uuid__in=timesheet_entries.values_list('task_uuid', flat=True)
                )
            }

            # Group by task and day
            task_hours = {}
            daily_hours = [{'billable': 0, 'non_billable': 0} for _ in range(7)]

            for entry in timesheet_entries:
                day_index = (entry.entry_date.date() - week_start).days
                hours = entry.minutes / 60

                # Add to daily totals based on billable status
                is_billable = tasks.get(entry.task_uuid, False)
                if is_billable:
                    daily_hours[day_index]['billable'] += hours
                else:
                    daily_hours[day_index]['non_billable'] += hours

                # Create unique key for job+task combination
                task_key = f"{entry.job_id}_{entry.task_uuid}"

                if task_key not in task_hours:
                    task_hours[task_key] = {
                        'job_id': entry.job_id,
                        'job_name': entry.job_name,
                        'task_uuid': entry.task_uuid,
                        'task_name': entry.task_name,
                        'daily_hours': [{'date': (week_start + timedelta(days=i)).strftime('%Y-%m-%d'), 
                                       'hours': 0,
                                       'notes': []} for i in range(7)]
                    }
                
                day_hours = task_hours[task_key]['daily_hours'][day_index]
                day_hours['hours'] += hours
                if entry.note:
                    day_hours['notes'].append(entry.note)

            # Format daily summary
            week_data = []
            for i in range(7):
                current_date = week_start + timedelta(days=i)
                week_data.append({
                    'date': current_date.strftime('%Y-%m-%d'),
                    'day': current_date.strftime('%a'),
                    'billable': daily_hours[i]['billable'],
                    'non_billable': daily_hours[i]['non_billable'],
                    'total': daily_hours[i]['billable'] + daily_hours[i]['non_billable']
                })

            return Response({
                'week_start': week_start.strftime('%Y-%m-%d'),
                'week_end': week_end.strftime('%Y-%m-%d'),
                'daily_hours': week_data,
                'task_hours': task_hours
            })
        except Exception as e:
            print(f"Error fetching weekly hours: {str(e)}")
            return Response({'error': str(e)}, status=500)
    
    elif request.method == 'POST':
        try:
            entries = request.data.get('entries', [])
            
            for entry in entries:
                task_uuid = entry['task_uuid']
                job_id = entry['job_id']
                
                for time_entry in entry['entries']:
                    # Create a new Timesheet entry
                    Timesheet.objects.create(
                        uuid=uuid.uuid4(),  # Generate a new UUID for each entry
                        staff_uuid=staff_uuid,
                        task_uuid=task_uuid,
                        job_id=job_id,
                        entry_date=datetime.strptime(time_entry['date'], '%Y-%m-%d'),
                        minutes=int(float(time_entry['hours']) * 60),  # Convert hours to minutes
                        note='\n'.join(time_entry['notes']) if time_entry['notes'] else '',
                        billable=True  # Default to billable
                    )
            
            return Response({'message': 'Timesheet submitted successfully'})
        except Exception as e:
            print(f"Error submitting timesheet: {str(e)}")
            return Response({'error': str(e)}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def all_jobs(request):
    try:
        print(f"Fetching all jobs")
        
        # Get all job IDs assigned to the staff member
        job_assignments = JobAssignedStaff.objects.all()
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
def client_detail(request, client_id):
    try:
        client = Client.objects.get(uuid=client_id)
        return Response({
            'uuid': client.uuid,
            'id': client.id,
            'name': client.name,
            'phone': client.phone,
            'email': client.email,
            'website': client.website,
            'address': client.address,
            'city': client.city,
            'region': client.region,
            'country': client.country,
            'post_code': client.post_code,
            'account_manager': client.account_manager_name,
            'job_manager': client.job_manager_name
        })
    except Client.DoesNotExist:
        return Response({'error': 'Client not found'}, status=404)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def client_jobs(request, client_id):
    try:
        jobs = Job.objects.filter(client_uuid=client_id).values(
            'job_id',
            'name',
            'state',
            'due_date'
        ).order_by('-due_date')
        
        return Response([{
            'job_number': job['job_id'],
            'name': job['name'],
            'status': job['state'],
            'due_date': job['due_date']
        } for job in jobs])
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def all_contacts(request):
    try:
        contacts = Contact.objects.all().values(
            'uuid',
            'name',
            'client__name',  # Get client name through relation
            'phone',
            'email'
        ).order_by('name')
        
        transformed_contacts = [{
            'uuid': contact['uuid'],
            'name': contact['name'],
            'client': contact['client__name'],
            'phone': contact['phone'],
            'email': contact['email']
        } for contact in contacts]
        
        return Response(transformed_contacts)
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def client_contacts(request, client_id):
    try:
        print(f"Fetching contacts for client: {client_id}")
        contacts = Contact.objects.filter(client_id=client_id).values(
            'uuid',
            'name',
            'phone',
            'email'
        ).order_by('name')
        
        print(f"Found {contacts.count()} contacts")
        return Response(list(contacts))
    except Exception as e:
        print(f"Error in client_contacts: {str(e)}")
        return Response({'error': str(e)}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def job_tasks(request, job_id):
    try:
        job = Job.objects.get(job_id=job_id)
        
        tasks = Task.objects.filter(job=job).values(
            'id',
            'uuid',  # Add UUID to the response
            'name',
            'estimated_minutes'
        ).order_by('name')
        
        print(f"Found {tasks.count()} tasks for job {job_id}")
        return Response(list(tasks))
    except Job.DoesNotExist:
        return Response({'error': f'Job {job_id} not found'}, status=404)
    except Exception as e:
        print(f"Error in job_tasks: {str(e)}")
        return Response({'error': str(e)}, status=500)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_timesheet(request, staff_uuid):
    try:
        entries = request.data.get('entries', [])
        print(f"Received entries: {entries}")
        
        for entry in entries:
            task_uuid = entry['task_uuid']
            job_id = entry['job_id']
            job_name = Job.objects.get(job_id=job_id).name
            
            print(f"Processing entry - Task UUID: {task_uuid}, Job ID: {job_id}, Job Name: {job_name}")

            try:
                staff = Staff.objects.get(uuid=staff_uuid)
                staff_name = staff.name
                
                try:
                    task = Task.objects.get(uuid=task_uuid)
                    task_name = task.name
                    print(f"Found task: {task_name}")
                except Task.DoesNotExist:
                    print(f"Task not found with UUID: {task_uuid}")
                    return Response(
                        {'error': f'Task not found with UUID: {task_uuid}'}, 
                        status=404
                    )
                
                for time_entry in entry['entries']:
                    entry_date = datetime.strptime(time_entry['date'], '%Y-%m-%d')
                    minutes = int(float(time_entry['hours']) * 60)
                    notes = '\n'.join(time_entry['notes']) if time_entry['notes'] else ''

                    # Try to find an existing entry for this task, date, and staff member
                    existing_entry = Timesheet.objects.filter(
                        staff_uuid=staff_uuid,
                        task_uuid=task_uuid,
                        job_id=job_id,
                        entry_date=entry_date
                    ).first()

                    if existing_entry:
                        print(f"Updating existing entry for date: {time_entry['date']}")
                        # Update existing entry if minutes or notes have changed
                        if existing_entry.minutes != minutes or existing_entry.note != notes:
                            existing_entry.minutes = minutes
                            existing_entry.note = notes
                            existing_entry.save()
                    else:
                        print(f"Creating new entry for date: {time_entry['date']}")
                        # Create new entry only if it doesn't exist
                        Timesheet.objects.create(
                            uuid=uuid.uuid4(),
                            staff_uuid=staff_uuid,
                            staff_name=staff_name,
                            task_name=task_name,
                            task_uuid=task_uuid,
                            job_id=job_id,
                            job_name=job_name,
                            entry_date=entry_date,
                            minutes=minutes,
                            note=notes,
                            billable=True
                        )

            except Staff.DoesNotExist:
                print(f"Staff not found with UUID: {staff_uuid}")
                return Response(
                    {'error': f'Staff not found with UUID: {staff_uuid}'}, 
                    status=404
                )
        
        return Response({'message': 'Timesheet submitted successfully'})
    except Exception as e:
        print(f"Error submitting timesheet: {str(e)}")
        print(f"Request data: {request.data}")
        return Response(
            {'error': f'Failed to submit timesheet: {str(e)}'}, 
            status=500
        )