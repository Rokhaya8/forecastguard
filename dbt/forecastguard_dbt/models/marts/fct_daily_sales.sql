select
    order_date,
    count(*) as number_of_orders,
    sum(quantity) as total_quantity,
    sum(total_amount) as total_revenue,
    avg(total_amount) as avg_order_value
from {{ ref('stg_orders') }}
group by order_date
order by order_date