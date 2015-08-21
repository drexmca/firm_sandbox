'''
------------------------------------------------------------------------
Last updated: 7/13/2015

Calculates steadX state of OLG model with S age cohorts, J tXpes, mortalitX risk

This pX-file calls the following other file(s):

This pX-file creates the following other file(s):
    (make sure that an OUTPUT folder exists)
            OUTPUT/
------------------------------------------------------------------------
'''

# Packages
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import time
import scipy.optimize as opt
import pickle
#import income
#import demographics
import numpy.polynomial.polynomial as poly



'''
------------------------------------------------------------------------
Setting up the Model
------------------------------------------------------------------------
S            = number of periods an individual lives
J            = number of different ability groups
T            = number of time periods until steady state is reached
bin_weights  = percent of each age cohort in each ability group
starting_age = age of first members of cohort
ending age   = age of the last members of cohort
E            = number of cohorts before S=1
beta_annual  = discount factor for one year
beta         = discount factor for each age cohort
sigma        = coefficient of relative risk aversion
alpha        = capital share of income
nu_init      = contraction parameter in steady state iteration process
               representing the weight on the new distribution gamma_new
A            = total factor productivity parameter in firms' production
               function
delta_annual = depreciation rate of capital for one year
delta        = depreciation rate of capital for each cohort
ctilde       = minimum value amount of consumption
bqtilde      = minimum bequest value
ltilde       = measure of time each individual is endowed with each
               period
chi_n        = discount factor of labor
chi_b        = discount factor of incidental bequests
eta          = Frisch elasticitX of labor supply
g_y_annual   = annual growth rate of technology
g_y          = growth rate of technologX for one cohort
TPImaxiter   = Maximum number of iterations that TPI will undergo
TPImindist   = Cut-off distance between iterations for TPI
------------------------------------------------------------------------
'''

#computational parameters
maxiter = 1000
mindist_SS = 1e-9
mu = 0.01



# Parameters
sigma = 1.9 # coeff of relative risk aversion for hh
beta = 0.98 # discount rate
alpha = np.array([0.29, 1.0-0.29]) # preference parameter - share of good i in composite consumption, shape =(I,), shares must sum to 1
cbar = np.array([0.000, 0.000]) # min cons of each of I goods, shape =(I,)
#delta = np.array([0.1, 0.1]) # depreciation rate
#delta = np.array([0.1, 0.12]) # depreciation rate
delta = np.array([0.1, 0.12, 0.15]) # depreciation rate, shape =(M,)
A = 1.0 # Total factor productivity
#gamma = np.array([0.3, 0.25]) # capital's share of output
#gamma = np.array([0.3, 0.3]) # capital's share of output
gamma = np.array([0.3, 0.25, 0.4]) # capital's share of output, shape =(M,)
#xi = np.array([[0.2, 0.8],[0.3, 0.7]]) # fixed coeff input-output matrix
#pi = np.array([[0.5, 0.5],[0.1, 0.9]]) # fixed coeff pce-bridge matrix relating output and cons goods
#pi = np.array([[1.0, 0.0],[0.0, 1.0]]) # fixed coeff pce-bridge matrix relating output and cons goods
xi = np.array([[0.2, 0.6, 0.2],[0.0, 0.2, 0.8], [0.6, 0.2, 0.2] ]) # fixed coeff input-output matrix, shape =(M,M)
#xi = np.array([[1.0, 0.0],[0.0, 1.0]]) # fixed coeff input-output matrix
pi = np.array([[0.4, 0.3, 0.3],[0.1, 0.8, 0.1]]) # fixed coeff pce-bridge matrix relating output and cons goods, shape =(I,M)
#xi = np.array([[1.0, 0.0],[0.0, 1.0]]) # fixed coeff input-output matrix
#xi = np.array([[0.0, 1.0],[0.0, 1.0]]) # fixed coeff input-output matrix
#epsilon = np.array([0.6, 0.6]) # elasticity of substitution between capital and labor
epsilon = np.array([0.55, 0.6, 0.62]) # elasticity of substitution between capital and labor, shape =(M,)
nu = 2.0 # elasticity of labor supply 
chi_n = 0.5 #utility weight, disutility of labor
chi_b = 0.2 #utility weight, warm glow bequest motive
ltilde = 1.0 # maximum hours
e = np.array([0.5, 1.0, 1.2, 1.7]) # effective labor units for the J types, shape =(J,)
#e = [1.0, 1.0, 1.0, 1.0] # effective labor units for the J types
S = 5 # periods in life of hh
J = 4 # number of lifetime income groups
I = 2 # number of consumption goods
M = 3 # number of production industries
surv_rate = np.array([0.99, 0.98, 0.6, 0.4, 0.0]) # probability of surviving to next period, shape =(S,)
#surv_rate = np.array([1.0, 1.0, 1.0, 1.0, 0.0]) # probability of surviving to next period
mort_rate = 1.0-surv_rate # probability of dying at the end of current period
surv_rate[-1] = 0.0
mort_rate[-1] = 1.0
surv_mat = np.tile(surv_rate.reshape(S,1),(1,J)) # matrix of survival rates
mort_mat = np.tile(mort_rate.reshape(S,1),(1,J)) # matrix of mortality rates
surv_rate1 = np.ones((S,1))# prob start at age S
surv_rate1[1:,0] = np.cumprod(surv_rate[:-1], dtype=float)
omega = np.ones((S,J))*surv_rate1# number of each age alive at any time
lambdas = np.array([0.5, 0.2, 0.2, 0.1])# fraction of each cohort of each type, shape =(J,)
weights = omega*lambdas/((omega*lambdas).sum()) # weights - dividing so weights sum to 1

# Functions and Definitions

print('checking omega')
omega2 = np.ones((S,1))# prob start at age S
omega2[1:,0] = np.cumprod(surv_rate[:-1], dtype=float)
print((omega[:,0].reshape(S,1)-omega2.reshape(S,1)).max())

def perc_dif_func(simul, data):
    '''
    Used to calculate the absolute percent difference between the data
    moments and model moments
    '''
    frac = (simul - data)/data
    output = np.abs(frac)
    return output

def get_X(K, L):
    '''
    Parameters: Aggregate capital, Aggregate labor

    Returns:    Aggregate output
    '''
    #X = (K ** alpha) * (L ** (1 - alpha))
    X = (A * (((gamma**(1/epsilon))*(K**((epsilon-1)/epsilon))) + 
          (((1-gamma)**(1/epsilon))*(L**((epsilon-1)/epsilon))))**(epsilon/(epsilon-1)))
    return X


def get_w(X, L, p):
    '''
    Parameters: Aggregate output, Aggregate labor

    Returns:    Returns to labor
    '''
    #w = (1 - alpha) * X / L
    w = p*((A**((epsilon-1)/epsilon))*((((1-gamma)*X)/L)**(1/epsilon))) 

    return w


def get_r(X, K, p):
    '''
    Parameters: Aggregate output, Aggregate capital

    Returns:    Returns to capital
    '''
    #r = (alpha * (X / K)) - delta
    r = p*((A**((epsilon-1)/epsilon))*(((gamma*X)/K)**(1/epsilon))) - delta

    return r


def get_L(n):
    '''
    Parameters: n 

    Returns:    Aggregate labor
    '''
    L = np.sum(weights*(n*e))
    return L
    
def get_K(k):
    '''
    Parameters: k 

    Returns:    Aggregate capital
    '''
    K_constr = False
    K = np.sum(weights*k)
    if K <= 0:
        print 'b matrix and/or parameters resulted in K<=0'
        K_constr = True
    return K, K_constr

def get_C(c_i):
    '''
    Parameters: c 

    Returns:    Aggregate consumption
    '''
    C = (np.tile(weights,(I,1,1))*c_i).sum(2).sum(1)    

    return C

def get_p(r, w):
    '''
    Generates price of consumption producer output

    Returns: p_c
    '''
    p = (((1-gamma)*((w/A)**(1-epsilon)))+(gamma*(((r+delta)/A)**(1-epsilon))))**(1/(1-epsilon))

    return p

def get_p_c(p):
    '''
    Generates price of consumption good

    Returns: p_c
    '''
    p_c = np.dot(pi,p)
    return p_c
    
def get_p_tilde(p_c):
    
    p_tilde = ((p_c/alpha)**alpha).prod()
    return p_tilde


def get_sum_Xk(r,p,X):

    x_sum = (gamma*X*((((r+delta)/p)*(A**((1-epsilon)/epsilon)))**(-1*epsilon))).sum()-(gamma*X*((((r+delta)/p)*(A**((1-epsilon)/epsilon)))**(-1*epsilon)))
    return x_sum 

def get_sum_Xl(w,p,X):

    x_sum = ((1-gamma)*X*(((w/p)*(A**((1-epsilon)/epsilon)))**(-1*epsilon))).sum()-((1-gamma)*X*(((w/p)*(A**((1-epsilon)/epsilon)))**(-1*epsilon)))
    return x_sum 

def MUc(c):
    '''
    Parameters: Consumption

    Returns:    Marginal Utility of Consumption
    '''
    output = c**(-sigma)
    return output


def MUl(n):
    '''
    Parameters: Labor

    Returns:    Marginal Utility of Labor
    '''
    output =  -chi_n * ((ltilde-n) ** (-nu))
    return output

def MUb(bq):
    '''
    Parameters: Intentional bequests

    Returns:    Marginal Utility of Bequest
    '''
    output = chi_b * (bq ** (-sigma))
    return output
    
def get_BQ(r, k, j):
    '''
    Parameters: Distribution of capital stock (SxJ)

    Returns:    Bequests by ability (Jx1)
    '''

    output = (1 + r) * (k*weights[:,j].reshape(S,1)*mort_mat[:,j].reshape(S,1)).sum()

    return output
    
def get_dist_bq(BQ, j):
    '''
    Parameters: Aggregate bequests by ability type

    Returns:    Bequests by age and ability
    '''
    output = np.tile(BQ/(weights[:,j].sum(0)),(S,1))

    return output

def get_cons(w, r, n, k, bq, p_c, p_tilde, j):
    '''
    Parameters: Aggregate bequests by ability type

    Returns:    Bequests by age and ability
    '''

    k0 = np.zeros((S,1))
    k0[1:,0] = k[:-1,0] # capital start period with

    output = (((1+r)*k0) + w*n*e[j] - k + bq - ((p_c*cbar).sum()))/p_tilde

    return output
    

def get_k_demand(w,r,X):
    '''
    Parameters: Interest rate
                Output

    Returns:    Demand for capital by the firm
    '''
    #output = (gamma*X)/(((r+delta)**epsilon)*(A**(1-epsilon)))
    output = (X/A)*(((gamma**(1/epsilon))+
              (((1-gamma)**(1/epsilon))*(((r+delta)*(1/w))**(epsilon-1))*
              (((1-gamma)/gamma)**((epsilon-1)/epsilon))))**(epsilon/(1-epsilon)))

    return output

def get_l_demand(w,r,K):
    '''
    Parameters: Wage rate
                Capital demand

    Returns:    Demand for labor by the firm
    '''
    output = K*((1-gamma)/gamma)*(((r+delta)/w)**epsilon)

    return output

def foc_k(r, c, j):
    '''
    Parameters:
        w        = wage rate (scalar)
        r        = rental rate (scalar)
        L_guess  = distribution of labor (SxJ array)
        K_guess  = distribution of capital at the end of period t (S x J array)
        bq       = distribution of bequests (S x J array)

    Returns:
        Value of foc error ((S-1)xJ array)
    '''

    error = MUc(c[:-1,0]) - (1+r)*beta*surv_mat[:-1,j]*MUc(c[1:,0])
    return error


def foc_l(w, L_guess, c, p_tilde, j):
    '''
    Parameters:
        w        = wage rate (scalar)
        r        = rental rate (scalar)
        L_guess  = distribution of labor (SxJ array)
        K_guess  = distribution of capital at the end of period t (S x J array)
        bq       = distribution of bequests (S x J array)

    Returns:
        Value of foc error (SxJ array)
    '''
    
    error = (w*MUc(c)*e[j])/p_tilde + MUl(L_guess) 
    return error

def foc_bq(K_guess, c, p_tilde):
    '''
    Parameters:
        w        = wage rate (scalar)
        r        = rental rate (scalar)
        e        = distribution of abilities (SxJ array)
        L_guess  = distribution of labor (SxJ array)
        K_guess  = distribution of capital in period t (S-1 x J array)
        bq       = distribution of bequests (S x J array)

    Returns:
        Value of Euler error.
    '''
    error = MUc(c[-1,:])/p_tilde -  MUb(K_guess[-1, :])
    return error


def solve_hh(guesses, r, w, p_c, p_tilde, j):
    '''
    Parameters: SS interest rate (r), SS wage rate (w)
    Returns:    Savings (Sx1)
                Labor supply (Sx1)    

    '''
    k = guesses[0: S].reshape((S, 1))
    n = guesses[S:].reshape((S, 1))        
    BQ = get_BQ(r, k, j)
    bq = get_dist_bq(BQ,j)
    c = get_cons(w, r, n, k, bq, p_c, p_tilde, j)
    error1 = foc_k(r, c, j) 
    error2 = foc_l(w, n, c, p_tilde, j) 
    error3 = foc_bq(k, c, p_tilde) 

    # Check and punish constraing violations
    mask1 = n <= 0
    mask2 = n > ltilde
    mask4 = c <= 0
    mask3 = k < 0
    #mask3 = k[:-1,0] <= 0
    error2[mask1] += 1e14
    error2[mask2] += 1e14
    error1[mask3[:-1,0]] += 1e14
    error1[mask4[:-1,0]] += 1e14
    if k[-1,0] < 0:
        error3 += 1e14
    if c[-1,0] <= 0:
        error3 += 1e14

    #error3[mask3[-1,0]] += 1e14


    #print('max euler error')
    #print(max(list(error1.flatten()) + list(error2.flatten()) + list(error3.flatten())))
    return list(error1.flatten()) + list(error2.flatten()) + list(error3.flatten()) 


def solve_output(guesses, w, r, X_c):
    X = guesses
    Inv = np.reshape(delta*get_k_demand(w,r,X),(1,M)) # investment demand - will differ not in SS
    errors = np.reshape(X_c  + np.dot(Inv,xi) - X,(M))
    return errors

def solve_k(guesses, p, K_s, X):
    K = guesses
    numerator = (p*((gamma*(X/K))**(1/epsilon))*(A**((epsilon-1)/1))-delta)[0]
    x_func = gamma*X*((((numerator+delta)/p)*(A**((1-epsilon)/1)))**(-1*epsilon))
    
    error = K-K_s+x_func.sum()-x_func

    # Check and punish constraing violations
    mask1 = K <= 0

    error[mask1] = 1e14

    #print 'solve k error: ', error
    #print 'k_m guess: ', K
    return error 

def solve_l(guesses, p, L_s, X):
    L = guesses
    numerator = (p*(((1-gamma)*(X/L))**(1/epsilon))*(A**(epsilon-1)))[0]
    x_func = (1-gamma)*X*(((numerator/p)*(A**((1-epsilon)/1)))**(-1*epsilon))
    
    error = L-L_s+x_func.sum()-x_func

    # Check and punish constraing violations
    mask1 = L <= 0

    error[mask1] = 1e14

    #print 'solve l error: ', error
    #print 'L_m guess: ', L
    return error 

def Steady_State(guesses, mu):
    '''
    Parameters: Steady state distribution of capital guess as array
                size SxJ and labor supply array of SxJ rss
    Returns:    Array of SxJ * 2 Euler equation errors
    '''
    
    r = guesses[0]
    w = guesses[1]
    

    dist = 10
    iteration = 0
    dist_vec = np.zeros(maxiter)
    
    # find prices of consumption goods
    p = get_p(r,w)
    p_c = get_p_c(p)
    p_tilde = get_p_tilde(p_c)
    #print 'prices ', p, p_c, p_tilde


    # Make initial guesses for capital and labor
    K_guess_init = np.ones((S, J)) * 0.05
    L_guess_init = np.ones((S, J)) * 0.3
    k = np.zeros((S,J)) # initialize k matrix
    n = np.zeros((S,J)) # initialize n matrix
    c = np.zeros((S, J))
    
    while (dist > mindist_SS) and (iteration < maxiter):

        for j in xrange(J):
            if j == 0:
                guesses = np.append(K_guess_init[:,j], L_guess_init[:,j])
            else:
                guesses = np.append(k[:,(j-1)], n[:,(j-1)])
            solutions = opt.fsolve(solve_hh, guesses, args=(r, w, p_c, p_tilde, j), xtol=1e-9, col_deriv=1)
            #out = opt.fsolve(solve_hh, guesses, args=(r, w, j), xtol=1e-9, col_deriv=1, full_output=1)
            #print'solution found flag', out[2], out[3]
            #solutions = out[0]
            k[:,j] = solutions[:S].reshape(S)
            n[:,j] = solutions[S:].reshape(S)
            BQ = get_BQ(r, k[:,j].reshape(S,1), j)
            bq = get_dist_bq(BQ, j).reshape(S,1)
            c[:,j] = get_cons(w, r, n[:,j].reshape(S,1), k[:,j].reshape(S,1), bq, p_c, p_tilde, j).reshape(S)

        c_i = ((p_tilde*np.tile(c,(2,1,1))*np.tile(np.reshape(alpha,(2,1,1)),(1,S,J)))/np.tile(np.reshape(p_c,(2,1,1)),(1,S,J)) 
                    + np.tile(np.reshape(cbar,(2,1,1)),(1,S,J)))
        #print 'c_i', c_i

        # Find total consumption of each good
        C = get_C(c_i)
        #print 'total cons by good: ', C

        # Find total demand for output from each sector from consumption
        X_c = np.dot(np.reshape(C,(1,I)),pi)
        guesses = X_c/I
        x_sol = opt.fsolve(solve_output, guesses, args=(w, r, X_c), xtol=1e-9, col_deriv=1)

        X = x_sol

        # find aggregate savings and labor supply
        K_s, K_constr = get_K(k)
        L_s = get_L(n)

        # Find factor demand from each industry as a function of factor supply
        #K_d = K_s - get_sum_Xk(r,p,X)
        #L_d = L_s - get_sum_Xl(w,p,X)
        #k_m_guesses = (X/X.sum())*K_s
        #l_m_guesses = (X/X.sum())*L_s
        #K_d = opt.fsolve(solve_k, k_m_guesses, args=(p, K_s, X), xtol=1e-9, col_deriv=1)
        #L_d = opt.fsolve(solve_l, l_m_guesses, args=(p, L_s, X), xtol=1e-9, col_deriv=1)


        #### Need to solve for labor and capital demand from each industry
        K_d = get_k_demand(w, r, X)
        L_d = get_l_demand(w, r, K_d)

        ## Solve for factor demands in a third way
        #r_vec = np.array([r, r, r])
        #K_d_3 = K_s - (gamma*X*((((r_vec+delta)/p)*(A**((1-epsilon)/1)))**(-1*epsilon))).sum() - (gamma*X*((((r_vec+delta)/p)*(A**((1-epsilon)/1)))**(-1*epsilon))) 
        #print ' three k diffs: ', K_d-K_d_3, K_d-K_d_check, K_d_3-K_d_check

        # get implied factor prices
        K_d_0 = max(K_s-K_d[1:].sum(),1e-1)
        L_d_0 = max(L_s-L_d[1:].sum(),1e-1)
        print 'K_d_0, L_d_0: ', K_d_0, L_d_0
        print 'K_s, L_s: ' , K_s, L_s
        print 'K_d: ', K_d 
        print 'L_d: ', L_d
        w_new = p[0]*((A**((epsilon[0]-1)/epsilon[0]))*((((1-gamma[0])*X[0])/L_d_0)**(1/epsilon[0]))) 
        r_new = p[0]*((A**((epsilon[0]-1)/epsilon[0]))*(((gamma[0]*X[0])/K_d_0)**(1/epsilon[0]))) - delta[0]
        #print 'all r_new values: ', get_r(X, K_d, p)
        #print 'all alt r_new values: ', get_r(X,K_d_check,p)
        #print 'alt r values: ', get_r(X,K_d_check,p)
        #print 'diff btwn r: ', get_r(X, K_d, p) - get_r(X,K_d_check,p)
        #print 'diff btwn k: ', K_d-K_d_check
        #print 'diff btwn w: ', get_w(X, L_d, p) - get_w(X,L_d_check,p)
        #print 'diff btwn l: ', L_d-L_d_check
        #print 'all w_new values: ', get_w(X, L_d, p)
        #print 'all alt w_new values: ', get_w(X,L_d_check,p)

        #print 'r diffs', r-get_r(X[0],K_d[0]), r-get_r(X[1],K_d[1])
        #print 'market clearing: ', K_s - K_d.sum(),  L_s - L_d.sum()
        #print 'market clearing 2: ', K_s - K_d_check.sum(), L_s - L_d_check.sum()

        # Check labor and capital market clearing conditions
        #error1 = K_s - K_d.sum()
        #error2 = L_s - L_d.sum()
        error1 = r_new - r
        error2 = w_new - w
        #print 'errors: ', error1, error2
        print 'r, w: ', r,w
        print 'r_new, w_new: ', r_new,w_new

        r = mu*r_new + (1-mu)*r # so if r low, get low save, so low capital stock, so high mpk, so r_new bigger
        w = mu*w_new + (1-mu)*w

        #dist = np.array([perc_dif_func(r_new, r)]+[perc_dif_func(w_new, w)]).max()
        dist = np.absolute([r_new-r,w_new-w]).max()
        
        dist_vec[iteration] = dist
        if iteration > 10:
            if dist_vec[iteration] - dist_vec[iteration-1] > 0:
                mu /= 2.0
                print 'New value of mu:', mu
        iteration += 1
        print "Iteration: %02d" % iteration, " Distance: ", dist

 
    return [r, w]
    

# Solve SS
r_guess_init = 0.77
w_guess_init = 1.03
guesses = [r_guess_init, w_guess_init]
solutions = Steady_State(guesses,mu)
rss = solutions[0]
wss = solutions[1]
print 'ss r, w: ', rss, wss

p_ss = get_p(rss,wss)
p_c_ss = get_p_c(p_ss)
p_tilde_ss = get_p_tilde(p_c_ss)
print 'SS cons prices: ', p_ss, p_c_ss, p_tilde_ss

K_guess_init = np.ones((S, J)) * 0.05
L_guess_init = np.ones((S, J)) * 0.3
kss = np.zeros((S, J))
nss = np.zeros((S, J))
css = np.zeros((S, J))
error1 = np.zeros((S-1,J)) # initialize foc k errors
error2 = np.zeros((S,J)) # initialize foc k errors
error3 = np.zeros((1,J)) # initialize foc k errors

for j in xrange(J):
    if j == 0:
        guesses = np.append(K_guess_init[:,j], L_guess_init[:,j])
    else:
        guesses = np.append(kss[:,(j-1)], nss[:,(j-1)])
    #solutions = opt.fsolve(solve_hh, guesses, args=(rss, wss, j), xtol=1e-9, col_deriv=1)
    out = opt.fsolve(solve_hh, guesses, args=(rss, wss, p_c_ss, p_tilde_ss, j), xtol=1e-9, col_deriv=1, full_output=1)
   # print'solution found flag', out[2], out[3]
    #print 'fsovle output: ', out[1]
    solutions = out[0]
    kss[:,j] = solutions[:S].reshape(S)
    nss[:,j] = solutions[S:].reshape(S)
    BQss = get_BQ(rss, kss[:,j].reshape(S,1), j)
    bqss = get_dist_bq(BQss, j).reshape(S,1)
    css[:,j] = get_cons(wss, rss, nss[:,j].reshape(S,1), kss[:,j].reshape(S,1), bqss, p_c_ss, p_tilde_ss, j).reshape(S)
    # check Euler errors
    error1[:,j] = foc_k(rss, css[:,j].reshape(S,1), j).reshape(S-1) 
    error2[:,j] = foc_l(wss, nss[:,j].reshape(S,1), css[:,j].reshape(S,1), p_tilde_ss, j).reshape(S) 
    error3[:,j] = foc_bq(kss[:,j].reshape(S,1), css[:,j].reshape(S,1), p_tilde_ss)

c_i_ss = ((p_tilde_ss*np.tile(css,(2,1,1))*np.tile(np.reshape(alpha,(2,1,1)),(1,S,J)))/np.tile(np.reshape(p_c_ss,(2,1,1)),(1,S,J)) 
                + np.tile(np.reshape(cbar,(2,1,1)),(1,S,J)))
# Find total consumption of each good
C_ss = get_C(c_i_ss)

# Find total demand for output from each sector from consumption
X_c_ss = np.dot(np.reshape(C_ss,(1,I)),pi)

print 'X_c_ss', X_c_ss

guesses = [X_c_ss/I]
x_sol_ss = opt.fsolve(solve_output, guesses, args=(wss, rss, X_c_ss), xtol=1e-9, col_deriv=1)

X_ss = x_sol_ss

# find aggregate savings and labor supply
K_s_ss, K_constr = get_K(kss)
L_s_ss = get_L(nss)

#### Need to solve for labor and capital demand from each industry
K_d_ss = get_k_demand(wss, rss, X_ss)
L_d_ss = get_l_demand(wss, rss, K_d_ss)

# Check labor and capital market clearing conditions
cap_diff = K_s_ss - K_d_ss.sum()
labor_diff = L_s_ss - L_d_ss.sum()
print 'Market clearing diffs: ', cap_diff, labor_diff

Yss = get_X(K_d_ss,L_d_ss)

#print 'cons: ', C1ss, C2ss
#print 'Kss: ', K1_d_ss, K2_d_ss
#print 'Lss: ', L1_d_ss, L2_d_ss
#print 'K/L: ', K1_d_ss/L1_d_ss, K2_d_ss/L2_d_ss
#print 'Xss: ', X1_ss, X2_ss, Y1ss, Y2ss

Inv_ss = delta*get_k_demand(wss,rss,X_ss) # investment demand - will differ not in SS

#X1ss_check = X_c_1_ss  + (I1ss*xi[0,0]) + (I2ss*xi[1,0])
#X2ss_check = X_c_2_ss  + (I1ss*xi[0,1]) + (I2ss*xi[1,1])
#print 'X1 check: ', X1_ss, X1ss_check
#print 'X2 check: ', X2_ss, X2ss_check


# Find factor demand from each industry as a function of factor supply
k_m_guesses = (X_ss/X_ss.sum())*K_s_ss
l_m_guesses = (X_ss/X_ss.sum())*L_s_ss
K_d_ss = opt.fsolve(solve_k, k_m_guesses, args=(p_ss, K_s_ss, X_ss), xtol=1e-9, col_deriv=1)
L_d_ss = opt.fsolve(solve_l, l_m_guesses, args=(p_ss, L_s_ss, X_ss), xtol=1e-9, col_deriv=1)
#K_d_ss = K_s_ss - get_sum_Xk(rss,p_ss,X_ss)
#L_d_ss = L_s_ss - get_sum_Xl(wss,p_ss,X_ss)

K_d_check_ss = get_k_demand(wss, rss, X_ss)
L_d_check_ss = get_l_demand(wss, rss, K_d_check_ss)


print 'diff btwn r_ss and implied r_ss: ', rss-get_r(X_ss, K_d_ss, p_ss)
print 'diff btwn r_ss and implied r_ss take 2: ', rss-get_r(X_ss, K_d_check_ss, p_ss)


print 'RESOURCE CONSTRAINT DIFFERENCE:'
print 'RC1: ', X_ss - Yss
print 'RC2: ', X_ss - X_c_ss- (np.dot(np.reshape(delta*K_d_check_ss,(1,M)),xi))
print 'RC3: ', X_ss - X_c_ss- (np.dot(np.reshape(delta*K_d_ss,(1,M)),xi))


print("Euler errors")
print(error1)
print(error2)
print(error3)

print 'kssmat: ', kss



