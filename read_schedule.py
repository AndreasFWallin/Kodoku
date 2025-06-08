import pandas as pd
import re
from typing import Dict, List, Set
from dataclasses import dataclass
from collections import defaultdict

@dataclass
class Assignment:
    staff_id: str
    day: int
    shift_id: str

class Schedule:
    def __init__(self, instance_data: dict):
        self.instance_data = instance_data
        self.assignments: List[Assignment] = []
        self.staff_assignments: Dict[str, List[Assignment]] = defaultdict(list)
        self.day_shift_assignments: Dict[tuple, List[Assignment]] = defaultdict(list)
        
        # Create a lookup dictionary for shifts
        self.shifts_dict = {shift['id']: shift for shift in instance_data['shifts']}
        
    def is_valid_assignment(self, assignment: Assignment) -> bool:
        """Check if an assignment is valid according to all constraints."""
        staff_id = assignment.staff_id
        day = assignment.day
        shift_id = assignment.shift_id
        
        # Get staff constraints
        staff = next(s for s in self.instance_data['staff'] if s['id'] == staff_id)
        
        # Check if staff is available on this day (not in days off)
        if day in self.instance_data['days_off'].get(staff_id, []):
            return False
            
        # Check shift limits
        if shift_id in staff['shift_limits']:
            current_count = sum(1 for a in self.staff_assignments[staff_id] 
                              if a.shift_id == shift_id)
            if current_count >= staff['shift_limits'][shift_id]:
                return False
        
        # Check consecutive shifts
        if len(self.staff_assignments[staff_id]) > 0:
            last_assignment = self.staff_assignments[staff_id][-1]
            if last_assignment.day == day - 1:
                if shift_id in self.shifts_dict[last_assignment.shift_id]['forbidden_following']:
                    return False
        
        # Check max consecutive shifts
        consecutive_count = 1
        for prev_day in range(day - 1, -1, -1):
            if any(a.day == prev_day for a in self.staff_assignments[staff_id]):
                consecutive_count += 1
            else:
                break
        if consecutive_count > staff['max_consecutive_shifts']:
            return False
            
        return True
    
    def greedy_schedule(self) -> bool:
        """Attempt to create a schedule using a greedy approach."""
        # Sort cover requirements by weight (higher weight = more important)
        cover_requirements = sorted(
            self.instance_data['cover_requirements'],
            key=lambda x: x['weight_under'],
            reverse=True
        )
        
        # Try to fill each requirement
        for req in cover_requirements:
            day = req['day']
            shift_id = req['shift_id']
            required = req['requirement']
            
            # Get current assignments for this day and shift
            current_assignments = self.day_shift_assignments.get((day, shift_id), [])
            needed = required - len(current_assignments)
            
            if needed <= 0:
                continue
                
            # Try to assign staff members
            for staff in self.instance_data['staff']:
                if needed <= 0:
                    break
                    
                # Create potential assignment
                potential_assignment = Assignment(
                    staff_id=staff['id'],
                    day=day,
                    shift_id=shift_id
                )
                
                # Check if assignment is valid
                if self.is_valid_assignment(potential_assignment):
                    # Make the assignment
                    self.assignments.append(potential_assignment)
                    self.staff_assignments[staff['id']].append(potential_assignment)
                    self.day_shift_assignments[(day, shift_id)].append(potential_assignment)
                    needed -= 1
            
            # If we couldn't fill all requirements, the schedule is incomplete
            if needed > 0:
                return False
                
        return True

def read_instance_file(file_path):
    """
    Read and parse an instance file for the scheduling problem.
    Returns a dictionary containing all sections of the instance.
    """
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Split content into sections
    sections = re.split(r'SECTION_', content)[1:]
    instance_data = {}
    
    for section in sections:
        section_name, *section_content = section.strip().split('\n', 1)
        section_content = section_content[0] if section_content else ""
        
        lines = [line.strip() for line in section_content.split('\n') 
                if line.strip() and not line.startswith('#')]
        
        if section_name == 'HORIZON':
            instance_data['horizon'] = int(lines[0])
            
        elif section_name == 'SHIFTS':
            shifts = []
            for line in lines:
                shift_id, length, forbidden = line.split(',')
                forbidden = forbidden.split('|') if forbidden else []
                shifts.append({
                    'id': shift_id,
                    'length': int(length),
                    'forbidden_following': forbidden
                })
            instance_data['shifts'] = shifts
        
        elif section_name == 'SECTION_DAYS_OFF':
            days_off = {}
            for line in lines:
                staff_id, *days = line.split(',')
                days_off[staff_id] = [int(day) for day in days]
            instance_data['days_off'] = days_off
            
        elif section_name == 'STAFF':
            staff = []
            for line in lines:
                parts = line.split(',')
                staff_id = parts[0]
                shift_limits = parts[1].split('|')
                shift_limits_dict = {}
                for limit in shift_limits:
                    if '=' in limit:
                        shift, max_count = limit.split('=')
                        shift_limits_dict[shift] = int(max_count)
                
                # Create staff entry with all fields
                staff_entry = {
                    'id': staff_id,
                    'shift_limits': shift_limits_dict,
                    'max_shifts': int(parts[2]),
                    'max_total_minutes': int(parts[3]),
                    'min_total_minutes': int(parts[4]),
                    'max_consecutive_shifts': int(parts[5]),
                    'min_consecutive_shifts': int(parts[6]),
                    'min_consecutive_days_off': int(parts[7])
                }
                
                # Add max_weekends if it exists
                if len(parts) > 8:
                    staff_entry['max_weekends'] = int(parts[8])
                
                staff.append(staff_entry)
            instance_data['staff'] = staff
            
        elif section_name == 'DAYS_OFF':
            days_off = {}
            for line in lines:
                staff_id, *days = line.split(',')
                days_off[staff_id] = [int(day) for day in days]
            instance_data['days_off'] = days_off


        # LOSS FUNCTION INPUT
        elif section_name == 'SHIFT_ON_REQUESTS':
            shift_on_requests = []
            for line in lines:
                staff_id, day, shift_id, weight = line.split(',')
                shift_on_requests.append({
                    'staff_id': staff_id,
                    'day': int(day),
                    'shift_id': shift_id,
                    'weight': int(weight)
                })
            instance_data['shift_on_requests'] = shift_on_requests
            
        elif section_name == 'SHIFT_OFF_REQUESTS':
            shift_off_requests = []
            for line in lines:
                staff_id, day, shift_id, weight = line.split(',')
                shift_off_requests.append({
                    'staff_id': staff_id,
                    'day': int(day),
                    'shift_id': shift_id,
                    'weight': int(weight)
                })
            instance_data['shift_off_requests'] = shift_off_requests
            
        elif section_name == 'COVER':
            cover_requirements = []
            for line in lines:
                day, shift_id, requirement, weight_under, weight_over = line.split(',')
                cover_requirements.append({
                    'day': int(day),
                    'shift_id': shift_id,
                    'requirement': int(requirement),
                    'weight_under': int(weight_under),
                    'weight_over': int(weight_over)
                })
            instance_data['cover_requirements'] = cover_requirements
    
    return instance_data

def main():
    # Example usage
    file_path = "instances1_24/instances1_24/Instance24.txt"
    instance_data = read_instance_file(file_path)
    
    # Print some basic information about the instance
    print(f"Horizon: {instance_data['horizon']} days")
    print(f"Number of shifts: {len(instance_data['shifts'])}")
    print(f"Number of staff: {len(instance_data['staff'])}")
    print(f"Number of shift on requests: {len(instance_data['shift_on_requests'])}")
    print(f"Number of shift off requests: {len(instance_data['shift_off_requests'])}")
    print(f"Number of cover requirements: {len(instance_data['cover_requirements'])}")
    
    # Try to create a schedule
    schedule = Schedule(instance_data)
    success = schedule.greedy_schedule()
    
    if success:
        print("\nSuccessfully created a schedule!")
        print(f"Total assignments made: {len(schedule.assignments)}")
        
        # Print some statistics about the schedule
        staff_assignments = defaultdict(int)
        for assignment in schedule.assignments:
            staff_assignments[assignment.staff_id] += 1
            
        print("\nAssignments per staff member:")
        for staff_id, count in sorted(staff_assignments.items()):
            print(f"{staff_id}: {count} assignments")
    else:
        print("\nFailed to create a complete schedule.")

if __name__ == "__main__":
    main()