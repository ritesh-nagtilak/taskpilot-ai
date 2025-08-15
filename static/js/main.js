document.addEventListener('DOMContentLoaded', function() {

    document.querySelectorAll('a[href*="delete_task"]').forEach(link => {
        link.addEventListener('click', function(e) {
            if (!confirm('Are you sure you want to delete this task?')) {
                e.preventDefault();
            }
        });
    });

    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', function(e) {
            const titleInput = form.querySelector('#title');
            if (titleInput && titleInput.value.trim().length < 3) {
                alert('Task title must be at least 3 characters long.');
                e.preventDefault();
            }
        });
    });

    const dueDateInput = document.getElementById('due_date');
    if (dueDateInput) {
        dueDateInput.addEventListener('change', function() {
            const selectedDate = new Date(this.value);
            const today = new Date();
            today.setHours(0, 0, 0, 0);

            if (selectedDate < today) {
                alert('Due date cannot be in the past.');
                this.value = '';
            }
        });
    }

    const currentPath = window.location.pathname;
    document.querySelectorAll('.nav-link').forEach(link => {
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
        }
    });

});
