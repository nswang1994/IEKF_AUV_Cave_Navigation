from import_data import imu_data, dvl_data, imu_bias_data, depth_data, odom_data
import numpy as np
from scipy.linalg import  expm, block_diag
from riekf import Right_IEKF
from plot_ekf_results import plot_time_series, plot_2d, plot_3d

def skew(omega):
    # Assume phi is a 3x1 vector
    return np.array([[        0, -omega[2],  omega[1]],
                     [ omega[2],         0, -omega[0]],
                     [-omega[1],  omega[0],         0]])

def gamma_0(phi):
    '''
    Assume phi comes in vector form
    '''
    return expm(skew(phi))

def gamma_1(phi):
    '''
    Assume phi comes in vector form
    '''
    nphi = np.linalg.norm(phi)
    sphi = skew(phi)
    return np.eye(3) + ((1-np.cos(nphi))/(nphi**2))*sphi + ((nphi-np.sin(nphi))/(nphi**3))*np.matmul(sphi,sphi)

def gamma_2(phi):
    '''
    Assume phi comes in vector form
    '''
    nphi = np.linalg.norm(phi)
    sphi = skew(phi)
    return 0.5*np.eye(3) + ((nphi-np.sin(nphi))/(nphi**3))*sphi + ((nphi**2 + 2*np.cos(nphi) - 2)/(2*(nphi**4)))*np.matmul(sphi,sphi)

def imu_dynamics(state, inputs, dt):
    Rk = state[:3,:3]
    vk = state[:3,3]
    pk = state[:3,4]
    # print(state)
    # Assume matrix form for inputs
    omega_k = inputs[:3,:3]   #3x3
    ak = inputs[:3,3]         #3x1

    # add bias
    # b_g = imu_bias_data.z.T[]
    # omega_k_bias = omega_k - b_g 

    g = np.array([0, 0, 9.80665])  # may need to make negative

    # Rk1 = np.matmul(Rk,gamma_0(omega_k*dt))
    # vk1 = vk + np.matmul(np.matmul(Rk,gamma_1(omega_k*dt)),ak)*dt + g*dt
    # pk1 = pk + vk*dt + np.matmul(np.matmul(Rk,gamma_2(omega_k*dt)),ak)*(dt**2) + 0.5*g*(dt**2)
    Rk1 = np.matmul(Rk,expm(omega_k*dt))
    vk1 = vk + np.dot(Rk,ak)*dt + g*dt  # vk + np.dot(np.matmul(Rk,np.eye(3)),ak)*dt + g*dt
    pk1 = pk + vk*dt + np.dot(Rk*0.5,ak)*(dt**2) + 0.5*g*(dt**2)  # pk + vk*dt + np.dot(np.dot(Rk,0.5*np.eye(3)),ak)*(dt**2) + 0.5*g*(dt**2)

    new_state = np.eye(5)
    new_state[:3,:3] = Rk1
    new_state[:3,3]  = vk1
    new_state[:3,4]  = pk1
    # print(new_state)
    return new_state

def A_matrix():
    A = np.zeros((9,9))
    # A[3,1] = -9.80665
    # A[4,0] = 9.80665
    g = np.array([0, 0, 9.80665])
    A[3:6,0:3] = skew(g)
    A[6:,3:6] = np.eye(3)
    return A

def H_matrix(b): # Possibly nonconstant, but not likely we believe
    '''
    H is 5x9 real matrix satisfying
    H*Xi = -Xi^{\wedge}*b, where we expect 
    Xi = [Xi_omega1 Xi_omega2 Xi_omega3 Xi_a1 Xi_a2 Xi_a3 Xi_v1 Xi_v2 Xi_v3]^T
    and
    b = [0 0 0 1 0]^T
    where Xi_ak is the k acceleration component, corresponding to the k velocity
    component of the state, and likewise for Xi_vj to pj in the position.
    '''
    H = np.zeros((5,9))
    H[:3,3:6] = -np.eye(3)
    return H

def toy_example():
    dummy_input = np.zeros((9,1))  # input comes in form of 9x1 vector
    dummy_input[3] = 0.1  # 0.1 m/s^2 for linear acceleration in x
    dummy_input[5] = -9.80665  # stand-in for gravity
    dummy_correction = np.array([-0.1, 0, 0, 1, 0]).T  # given dt = 1, should be -0.1 m/s in x direction as observed from DVL
    b = np.array([0, 0, 0, 1, 0]).T  # second to last element needs to be 1 because of homogeneous tranformation formulation

    Q_omega = 0.1*np.eye(3)
    Q_a = 0.1*np.eye(3)
    Q = block_diag(Q_omega, Q_a, np.eye(3))

    DVL_cov = 0.1*np.eye(3)
    N = block_diag(DVL_cov, np.eye(2))  # needs to be 5x5 to match

    sys = {
        'f': imu_dynamics,
        'A': A_matrix(),
        'H': H_matrix,
        'Q': Q,
        'N': N,
    }
    # print(expm(A_matrix()*0.01))
    filt = Right_IEKF(sys)
    filt.prediction(dummy_input, 1)
    print(filt.X)
    filt.correction(dummy_correction, b)
    print(filt.X)

def data_example():
    b = np.array([0, 0, 0, 1, 0]).T  # second to last element needs to be 1 because of homogeneous tranformation formulation

    Q_omega = 0.1*np.eye(3)
    Q_a = 0.1*np.eye(3)
    Q = block_diag(Q_omega, Q_a, np.eye(3))

    DVL_cov = 0.1*np.eye(3)
    N = block_diag(DVL_cov, np.eye(2))  # needs to be 5x5 to match

    sys = {
        'f': imu_dynamics,
        'A': A_matrix(),
        'H': H_matrix,
        'Q': Q,
        'N': N,
    }

    filt = Right_IEKF(sys)
    # dt is from 0, so just need first timestep
    dt1 = imu_data.time[0,0] * 1e-9
    
    filt.prediction(imu_data.z[:,0], 0.1, imu_bias_data.z[:,0])
    if imu_data.time[0,0] <= dvl_data.time[0,0]:
        measurement = np.hstack((dvl_data.z[:,0], [1, 0]))
        filt.correction(measurement, b)

    # Need to collect predictions over time and ground truth (gt)
    all_X_pred = []
    all_X_gt = odom_data.z.T
    b_g = imu_bias_data.z

    for i in range(1, min(imu_data.l,dvl_data.l)):
        # Calculate proper dt
        dt = imu_data.time[0,i] - imu_data.time[0,i-1]
        dt = dt * 1e-9
        # dt = dt/1000000000
        # print(dt)
        filt.prediction(imu_data.z[:,i], dt, b_g[:,i])

        # Naive matching here, merely to avoid correcting with something that came beforehand
        if imu_data.time[0,i] <= dvl_data.time[0,i]:
            measurement = np.hstack((dvl_data.z[:,i], [1, 0]))
            filt.correction(measurement, b)

        # Save prediction from this iteration
        all_X_pred.append(filt.X[:3, 4])

    all_X_pred = np.array(all_X_pred)

    # print(all_X_gt[0, :])

    # Plot 3D position graph to check results
    # plot_3d([all_X_pred[:, 0], all_X_gt[:, 0]], 
    #         [all_X_pred[:, 1], all_X_gt[:, 1]], 
    #         [all_X_pred[:, 2], all_X_gt[:, 2]],
    #         'orientation_x', 'orientation_y', 'orientation_z',
    #         ['predicted', 'ground truth'],
    #         'RI-EKF Iteration 0 Results',
    #         save_dir='../')

    plot_2d([all_X_pred[:, 0], all_X_gt[:, 0]], 
            [all_X_pred[:, 1], all_X_gt[:, 1]], 
            'orientation_x', 'orientation_y', 
            ['predicted', 'ground truth'],
            'RI-EKF Iteration',
            save_dir='../'
            )


if __name__ == "__main__":
    data_example()