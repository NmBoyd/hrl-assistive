
#include "hrl_multimodal_anomaly_detection/pcl_filter.h"

PCLfilter::PCLfilter(const ros::NodeHandle &nh): nh_(nh)
{
    cloud_ptr_.reset (new pcl::PointCloud<pcl::PointXYZI>());
    filtered_cloud_ptr_.reset (new pcl::PointCloud<pcl::PointXYZI>());

    getParams();
    initComms();
}

PCLfilter::~PCLfilter()
{
}

void PCLfilter::getParams()
{
    XmlRpc::XmlRpcValue range_min;
    while (nh_.getParam("/hrl_feeding_task/pcl/min", range_min) == false)
        sleep(0.1);

    XmlRpc::XmlRpcValue range_max;
    while (nh_.getParam("/hrl_feeding_task/pcl/max", range_max) == false)
        sleep(0.1);

    x_min_ = range_min[0]; x_max_ = range_max[0];
    y_min_ = range_min[1]; y_max_ = range_max[1];
    z_min_ = range_min[2]; z_max_ = range_max[2];
}

void PCLfilter::initComms()
{
    // ROS Publisher and subscribers
    ros::Subscriber raw_pcl_sub_;

    filtered_pcl_pub_ = nh_.advertise<sensor_msgs::PointCloud2>("/hrl_feeding_task/camera/depth_registered_points", 1, true);

    pcl_sub_ = nh_.subscribe("/head_mount_kinect/depth_registred/points", 1, &PCLfilter::depthPointsCallback, this);

}

void PCLfilter::depthPointsCallback(const sensor_msgs::PointCloud2ConstPtr& msg)
{
    pcl::fromROSMsg (*msg, *cloud_ptr_);

    //// filtering
    // Create the filtering object
    pcl::PassThrough<pcl::PointXYZI> pass;
    pass.setInputCloud (cloud_ptr_);
    pass.setFilterFieldName ("x");
    pass.setFilterLimits (x_min_, x_max_);
    pass.filter (*filtered_cloud_ptr_);

    pass.setInputCloud (filtered_cloud_ptr_);
    pass.setFilterFieldName ("y");
    pass.setFilterLimits (y_min_, y_max_);
    pass.filter (*filtered_cloud_ptr_);

    pass.setInputCloud (filtered_cloud_ptr_);
    pass.setFilterFieldName ("z");
    pass.setFilterLimits (z_min_, z_max_);
    pass.filter (*filtered_cloud_ptr_);

    // pub
    sensor_msgs::PointCloud2 output_msg;
    pcl::toROSMsg(*filtered_cloud_ptr_, output_msg);
    filtered_pcl_pub_.publish(output_msg);    
}

int main(int argc, char **argv)
{
    ROS_INFO("PCL filtering program main()");
    ros::init(argc, argv, "pcl_filter");
    ros::NodeHandle n;

    PCLfilter filter_server(n);
    ros::spin();
}

